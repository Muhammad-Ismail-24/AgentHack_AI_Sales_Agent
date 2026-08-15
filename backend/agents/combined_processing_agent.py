"""Scores, matches a service, selects a decision maker, and writes an email for
every researched lead in as few LLM calls as possible.

Classifies leads in batches (one LLM call per BATCH_SIZE leads) instead of one
call per lead, mirroring filter_agent.py's proven pattern: a same-length JSON
array is the fast path, and anything shorter (truncated/malformed) falls back
to per-lead calls only for the leads the batch response didn't cover.

Decision-maker contacts are grounded in tools.hunter_email.find_emails() before
the prompt is built, and any primary_contact the model returns that isn't in
that lead's own fetched candidate list is discarded in favour of a real one —
the model is never trusted to invent an email address.

Either way, state['error'] is set when quota runs out so the pipeline status
reports the real reason instead of silently completing with 0 qualified leads.
"""

import asyncio
import json

from agents.llm_utils import call_llm_raw, is_quota_error
from agents.llm_utils import extract_json as _extract_json
from agents.llm_utils import extract_partial_array as _extract_partial_array
from config.prompts import BATCH_COMBINED_PROCESSING_PROMPT, COMBINED_PROCESSING_PROMPT
from config.settings import settings
from rag.retriever import query as rag_query
from tools import hunter_email
from tools.calendar_tool import generate_booking_link
from utils.logger import logger

# Generous headroom above MAX_LEADS_TO_RESEARCH — keeps this chunk-safe even
# if that setting is raised well past its current default later.
BATCH_SIZE = 10


def _fallback_contact(lead: dict) -> dict:
    domain = lead.get("domain", "")
    return {
        "name": "Hiring/Ops Team",
        "role": "Unknown",
        "email": f"info@{domain}" if domain else "",
    }


async def _prep_lead(lead: dict) -> dict:
    """Attach the non-LLM context (real Hunter contacts, booking link) each
    lead needs before prompting. Neither call touches the Gemini rate limiter
    — Hunter has its own (tools/hunter_email.py). find_emails() blocks on
    that limiter internally, so it's dispatched via asyncio.to_thread here
    rather than called directly, or a throttled wait would freeze the event
    loop for every other request the server is handling.
    """
    domain = lead.get("domain", "")
    contacts = await asyncio.to_thread(hunter_email.find_emails, domain)
    available_contacts = (
        [
            {
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "role": c.get("position", ""),
                "email": c.get("email", ""),
            }
            for c in contacts
        ]
        if contacts
        else []
    )
    return {
        **lead,
        "_available_contacts": available_contacts,
        "_booking_link": generate_booking_link(lead.get("company_name", "Prospect")),
    }


def _research_block(lead: dict) -> dict:
    # Drop the raw scraped text from the JSON blob sent to the LLM — it can
    # be huge; keep the fields the prompt actually needs.
    return {
        "company_name": lead.get("company_name"),
        "url": lead.get("url"),
        "snippet": lead.get("snippet"),
        "apollo_data": lead.get("apollo_data"),
        "news_snippets": lead.get("news_snippets"),
        "website_excerpt": (lead.get("scraped_text") or "")[:2000],
    }


def _apply_result(lead: dict, result: dict) -> dict:
    """Merge one lead's parsed LLM result onto the lead dict.

    The decision-maker pick is re-grounded against that lead's own Hunter
    results here — never trusted straight off the model, batched or not.
    """
    qual = result.get("qualification", {}) if isinstance(result, dict) else {}
    score = int(qual.get("score", 0)) if qual else 0

    merged = {
        **lead,
        "score": score,
        "explanation": qual.get("explanation", ""),
        "top_reasons": qual.get("top_reasons", []),
        "red_flags": qual.get("red_flags", []),
    }

    if score >= settings.MIN_QUALIFICATION_SCORE:
        match = result.get("service_match", {}) or {}
        merged["recommended_service"] = match.get("recommended_service", "")
        merged["pitch_angle"] = match.get("pitch_angle", "")
        merged["why_it_fits"] = match.get("why_it_fits", "")

        dm = result.get("decision_maker", {}) or {}
        primary_contact = dm.get("primary_contact") or {}
        available = lead.get("_available_contacts") or []
        valid_emails = {c["email"].lower() for c in available if c.get("email")}
        if (primary_contact.get("email") or "").lower() not in valid_emails:
            primary_contact = available[0] if available else _fallback_contact(lead)
        merged["primary_contact"] = primary_contact

        email = result.get("email", {}) or {}
        merged["subject"] = email.get("subject", "")
        merged["body"] = email.get("body", "")
        merged["booking_link"] = lead.get("_booking_link", "")

    return merged


async def _process_lead_individually(
    lead: dict, icp_json: str, company_knowledge: str
) -> dict | None:
    """One-call-per-lead fallback, used only when a batch response is unusable."""
    prompt = COMBINED_PROCESSING_PROMPT.format(
        company_research=json.dumps(_research_block(lead)),
        icp=icp_json,
        company_knowledge=company_knowledge,
        booking_link=lead.get("_booking_link", ""),
        sender_company_name=settings.SENDER_COMPANY_NAME,
    )
    raw_text = await call_llm_raw(prompt)
    result = _extract_json(raw_text)
    if not isinstance(result, dict) or "qualification" not in result:
        logger.warning(
            f"combined_processing_agent: bad per-lead result for "
            f"'{lead.get('company_name', '?')}', skipping"
        )
        return None
    return _apply_result(lead, result)


async def _process_chunk(
    chunk: list[dict], icp_json: str, company_knowledge: str
) -> tuple[list[dict], bool]:
    """Process one chunk of leads with a single batched LLM call.

    A same-length JSON array is the fast path. Anything else falls back to
    per-lead calls only for the leads the batch response didn't cover —
    never the whole chunk. Returns (processed, quota_exhausted).
    """
    leads_block = "\n".join(
        f"{i}. Company research: {json.dumps(_research_block(lead))}\n"
        f"   Available contacts: {json.dumps(lead.get('_available_contacts', []))}\n"
        f"   Booking link: {lead.get('_booking_link', '')}"
        for i, lead in enumerate(chunk, start=1)
    )
    prompt = BATCH_COMBINED_PROCESSING_PROMPT.format(
        icp=icp_json,
        company_knowledge=company_knowledge,
        sender_company_name=settings.SENDER_COMPANY_NAME,
        leads_block=leads_block,
        lead_count=len(chunk),
    )

    try:
        raw_text = await call_llm_raw(prompt)
    except Exception as e:
        if is_quota_error(e):
            logger.warning("combined_processing_agent: Gemini quota exhausted on batch call, stopping")
            return [], True
        logger.warning(f"combined_processing_agent: batch call failed ({e}), falling back to per-lead")
        raw_text = None

    result = _extract_json(raw_text) if raw_text else None

    if isinstance(result, list) and len(result) == len(chunk):
        processed = [
            _apply_result(lead, verdict)
            for lead, verdict in zip(chunk, result)
            if isinstance(verdict, dict)
        ]
        return processed, False

    # Full parse failed — salvage whatever leading objects are well-formed
    # (covers truncation) before falling back per-lead for the remainder.
    partial = _extract_partial_array(raw_text) if raw_text else []
    covered = min(len(partial), len(chunk))
    if covered:
        logger.warning(
            f"combined_processing_agent: batch response only covered {covered}/{len(chunk)} leads "
            "(truncated or malformed) — recovered the parseable prefix"
        )
    elif raw_text is not None:
        logger.warning(
            f"combined_processing_agent: batch response unusable, 0/{len(chunk)} leads recovered — "
            "falling back to per-lead for the whole chunk"
        )

    processed = [
        _apply_result(lead, verdict)
        for lead, verdict in zip(chunk[:covered], partial[:covered])
        if isinstance(verdict, dict)
    ]

    for lead in chunk[covered:]:
        try:
            result = await _process_lead_individually(lead, icp_json, company_knowledge)
        except Exception as e:
            if is_quota_error(e):
                logger.warning("combined_processing_agent: Gemini quota exhausted mid per-lead fallback, stopping")
                return processed, True
            logger.warning(
                f"combined_processing_agent: failed to process lead "
                f"'{lead.get('company_name', '?')}': {e}"
            )
            continue
        if result is not None:
            processed.append(result)

    return processed, False


def _strip_internal_fields(lead: dict) -> dict:
    return {k: v for k, v in lead.items() if not k.startswith("_")}


async def run(state: dict) -> dict:
    """Read state['researched_leads']; batch-score/match/assign/write all of
    them in as few LLM calls as possible. Sets state['qualified_leads'] and
    state['outreach_queue'], and state['error'] if Gemini quota ran out
    partway through (so the pipeline doesn't silently report success).
    """
    try:
        researched_leads = state.get("researched_leads", []) or []
        icp = state.get("icp", {}) or {}
        collection = state.get("company_collection", "")

        company_knowledge = rag_query(
            "what services and solutions does our company offer", collection
        )
        icp_json = json.dumps(icp)

        prepped_leads = [await _prep_lead(lead) for lead in researched_leads]

        processed_leads: list[dict] = []
        quota_exhausted = False
        for start in range(0, len(prepped_leads), BATCH_SIZE):
            chunk = prepped_leads[start : start + BATCH_SIZE]
            results, quota_exhausted = await _process_chunk(chunk, icp_json, company_knowledge)
            processed_leads.extend(results)
            if quota_exhausted:
                break

        qualified_leads = [
            lead for lead in processed_leads if lead.get("score", 0) >= settings.MIN_QUALIFICATION_SCORE
        ]
        qualified_leads.sort(key=lambda x: x["score"], reverse=True)
        qualified_leads = [_strip_internal_fields(lead) for lead in qualified_leads]
        outreach_queue = qualified_leads

        state["qualified_leads"] = qualified_leads
        state["outreach_queue"] = outreach_queue

        if quota_exhausted:
            state["error"] = (
                "Gemini API quota exhausted during combined lead processing — "
                f"only {len(processed_leads)}/{len(researched_leads)} leads were processed "
                "before the run stopped. Wait for the daily quota to reset, or use a "
                "paid API key."
            )
            logger.error(f"combined_processing_agent: stopped early — {state['error']}")

        logger.info(
            f"combined_processing_agent: {len(qualified_leads)}/{len(researched_leads)} "
            f"leads processed successfully"
        )
        return state
    except Exception as e:
        logger.error(f"combined_processing_agent failed: {e}")
        return state
