"""Scores the lead, matches a service, selects a decision maker, and writes an email in one LLM call.

The contact is looked up, not generated. Hunter returns the real people at the
domain and the LLM only picks one of them; _resolve_contact then checks the
address it picked actually came from that list. An LLM cannot know somebody's
email address — left to invent one it produces a plausible-looking guess, and
outreach then goes to a stranger. When Hunter has nothing, the lead carries an
empty contact rather than a fabricated one.
"""

import asyncio
import json

from agents.llm_utils import GeminiQuotaExhausted, call_llm_json
from config.prompts import COMBINED_PROCESSING_PROMPT
from config.settings import settings
from rag.retriever import query as rag_query
from tools import hunter_email
from tools.calendar_tool import generate_booking_link
from utils.logger import logger

_EMPTY_CONTACT = {"name": "", "role": "", "email": ""}


def _resolve_contact(chosen: object, candidates: list[dict]) -> dict:
    """Accept the LLM's pick only if its email is one Hunter actually returned.

    Guards against the model ignoring the prompt and guessing an address
    (firstname@company.com and friends), which is the failure mode that
    silently sends outreach to people who never existed.
    """
    if not candidates:
        return dict(_EMPTY_CONTACT)

    by_email = {c["email"].lower(): c for c in candidates if c.get("email")}
    if not by_email:
        return dict(_EMPTY_CONTACT)

    picked = (chosen or {}).get("email", "") if isinstance(chosen, dict) else ""
    match = by_email.get(str(picked).strip().lower())
    if match is None:
        fallback = next(iter(by_email.values()))
        logger.warning(
            "combined_processing_agent: LLM returned contact email %r which Hunter "
            "never found — using the verified contact %r instead",
            picked, fallback["email"],
        )
        match = fallback

    # `or ""` rather than a .get default: Hunter returns the key present and
    # set to None for role addresses (info@, sales@), and a plain default only
    # applies when the key is absent — so the naive form rendered the contact
    # as the literal string "None None" in the Inbox and on the meeting card.
    name = f"{match.get('first_name') or ''} {match.get('last_name') or ''}".strip()
    return {
        "name": name,
        "role": match.get("position") or "",
        "email": match["email"],
    }


async def run(state: dict) -> dict:
    """Read state['researched_leads'], score them, match a service, find a decision
    maker, and write an email all in one go to save API calls.
    Updates state['qualified_leads'] and state['outreach_queue'].
    """
    try:
        researched_leads = state.get("researched_leads", []) or []
        icp = state.get("icp", {}) or {}
        collection = state.get("company_collection", "")

        company_knowledge = rag_query(
            "what services and solutions does our company offer", collection
        )

        qualified_leads = []
        outreach_queue = []
        # Leads the LLM actually scored vs. leads whose call failed. Zero
        # judged with N failures is a broken LLM, not a strict qualifier —
        # the two must not produce the same silent empty result.
        judged = 0
        failures: list[str] = []

        for lead in researched_leads:
            try:
                company_name = lead.get("company_name", "Prospect")
                booking_link = generate_booking_link(company_name)

                # Real contacts for this domain — the LLM picks from these
                # rather than inventing an address. Sync HTTP, so off-thread.
                candidates = await asyncio.to_thread(
                    hunter_email.find_emails, lead.get("domain", "")
                )
                available_contacts = [
                    {
                        "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip(),
                        "role": c.get("position") or "",
                        "email": c.get("email") or "",
                    }
                    for c in candidates
                    if c.get("email")
                ]
                if not available_contacts:
                    logger.warning(
                        "combined_processing_agent: no verified contact for '%s' "
                        "(domain=%r) — lead will carry an empty contact",
                        company_name, lead.get("domain", ""),
                    )

                research_for_prompt = {
                    "company_name": company_name,
                    "url": lead.get("url"),
                    "snippet": lead.get("snippet"),
                    "apollo_data": lead.get("apollo_data"),
                    "news_snippets": lead.get("news_snippets"),
                    "website_excerpt": (lead.get("scraped_text") or "")[:2000],
                }

                prompt = COMBINED_PROCESSING_PROMPT.format(
                    company_research=json.dumps(research_for_prompt),
                    icp=json.dumps(icp),
                    company_knowledge=company_knowledge,
                    booking_link=booking_link,
                    sender_company_name=settings.SENDER_COMPANY_NAME,
                    available_contacts=json.dumps(available_contacts),
                )

                result = await call_llm_json(prompt)
                if not isinstance(result, dict) or "qualification" not in result:
                    logger.warning(
                        f"combined_processing_agent: bad result for "
                        f"'{company_name}', skipping"
                    )
                    failures.append(f"unusable LLM response for '{company_name}'")
                    continue

                qual = result.get("qualification", {})
                score = int(qual.get("score", 0))
                judged += 1

                lead = {
                    **lead,
                    "score": score,
                    "explanation": qual.get("explanation", ""),
                    "top_reasons": qual.get("top_reasons", []),
                    "red_flags": qual.get("red_flags", []),
                }

                if score >= settings.MIN_QUALIFICATION_SCORE:
                    match = result.get("service_match", {})
                    lead["recommended_service"] = match.get("recommended_service", "")
                    lead["pitch_angle"] = match.get("pitch_angle", "")
                    lead["why_it_fits"] = match.get("why_it_fits", "")

                    dm = result.get("decision_maker", {})
                    lead["primary_contact"] = _resolve_contact(
                        dm.get("primary_contact"), candidates
                    )

                    email = result.get("email", {})
                    lead["subject"] = email.get("subject", "")
                    lead["body"] = email.get("body", "")
                    lead["booking_link"] = booking_link

                    qualified_leads.append(lead)
                    outreach_queue.append(lead)
                else:
                    logger.info(
                        f"combined_processing_agent: '{company_name}' disqualified "
                        f"(score {score} < {settings.MIN_QUALIFICATION_SCORE})"
                    )

            except GeminiQuotaExhausted as e:
                # Every further lead would burn retries on a call that is
                # guaranteed to fail — stop here, same as filter_agent does.
                failures.append(str(e))
                logger.error(
                    "combined_processing_agent: Gemini quota exhausted — "
                    f"stopping with {judged}/{len(researched_leads)} leads processed"
                )
                break
            except Exception as e:
                failures.append(str(e))
                logger.warning(
                    f"combined_processing_agent: failed to process lead "
                    f"'{lead.get('company_name', '?')}': {e}"
                )

        qualified_leads.sort(key=lambda x: x["score"], reverse=True)

        state["qualified_leads"] = qualified_leads
        state["outreach_queue"] = outreach_queue

        if failures and judged == 0 and researched_leads:
            # Nothing was scored at all. Append rather than overwrite —
            # filter_agent may already have recorded its own failure.
            message = (
                f"Lead processing failed: the LLM could not score any of the "
                f"{len(researched_leads)} researched leads "
                f"({len(failures)} call(s) failed). "
                f"Last error: {failures[-1][:200]}"
            )
            prior = state.get("error")
            state["error"] = f"{prior} | {message}" if prior else message
            logger.error(f"combined_processing_agent: {message}")
        elif failures:
            logger.warning(
                f"combined_processing_agent: {len(failures)} lead(s) skipped due "
                f"to LLM failures (last error: {failures[-1][:200]})"
            )

        logger.info(
            f"combined_processing_agent: {len(qualified_leads)}/{len(researched_leads)} "
            f"leads processed successfully"
        )
        return state
    except Exception as e:
        logger.error(f"combined_processing_agent failed: {e}")
        return state
