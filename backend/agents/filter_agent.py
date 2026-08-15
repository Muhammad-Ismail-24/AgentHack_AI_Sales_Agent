"""Cheap first-pass filtering — drops obvious non-fits before expensive research.

Classifies leads in batches (one LLM call per BATCH_SIZE leads) instead of one
call per lead — a raw_leads list of ~30 used to cost ~30 calls here alone,
which is most of a Gemini free-tier daily quota on its own.

A batch response can fail in two different ways, handled differently:
  - Quota exhausted (429): every further call is going to fail the same way,
    so the whole run stops calling the LLM immediately rather than retrying
    per-lead for nothing.
  - Truncated/malformed JSON (e.g. GEMINI_MAX_TOKENS cut the array off
    mid-object): salvaged as far as it parses via _extract_partial_array, and
    only the leads past the truncation point fall back to a per-lead call —
    not the whole chunk. A large chunk truncating used to mean up to
    BATCH_SIZE extra calls; now it's only the unparsed tail.

Either way, state['error'] is set when quota runs out so the pipeline status
reports the real reason instead of silently completing with 0 qualified leads.
"""

import json

from agents.llm_utils import call_llm_json, call_llm_raw
from agents.llm_utils import extract_json as _extract_json
from config.prompts import BATCH_FILTER_PROMPT, FILTER_PROMPT
from utils.logger import logger

# Kept small enough that a full batch's JSON array comfortably fits inside
# GEMINI_MAX_TOKENS — a 40-lead batch was observed truncating mid-response.
BATCH_SIZE = 15


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "ResourceExhausted" in type(exc).__name__ or "quota" in text.lower()


def _extract_partial_array(text: str) -> list[dict]:
    """Recover as many leading objects as possible from a truncated JSON array.

    Scans for top-level {...} blocks in order and stops at the first one that
    doesn't parse — which is exactly where a max-tokens cutoff lands, since
    everything before the cut is still well-formed JSON.
    """
    if not text:
        return []

    objects: list[dict] = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    break
                if not isinstance(obj, dict):
                    break
                objects.append(obj)
                start = None
    return objects


async def _filter_lead_individually(lead: dict, icp_json: str) -> tuple[bool, bool]:
    """One-call-per-lead fallback, used only when a batch response is unusable.

    Returns (is_fit, quota_exhausted).
    """
    try:
        prompt = FILTER_PROMPT.format(
            company_name=lead.get("company_name", ""),
            snippet=lead.get("snippet", ""),
            icp=icp_json,
        )
        result = await call_llm_json(prompt)
        return isinstance(result, dict) and result.get("is_potential_fit") is True, False
    except Exception as e:
        if _is_quota_error(e):
            logger.warning("filter_agent: Gemini quota exhausted mid per-lead fallback, stopping")
            return False, True
        logger.warning(
            f"filter_agent: failed to filter lead "
            f"'{lead.get('company_name', '?')}': {e}"
        )
        return False, False


async def _filter_chunk(chunk: list[dict], icp_json: str) -> tuple[list[dict], bool]:
    """Classify one chunk of leads with a single LLM call.

    A same-length JSON array is the fast path. Anything else falls back to
    per-lead calls only for the leads the batch response didn't cover —
    never the whole chunk. Returns (kept, quota_exhausted).
    """
    leads_block = "\n".join(
        f"{i}. {lead.get('company_name', '?')} — {lead.get('snippet', '')}"
        for i, lead in enumerate(chunk, start=1)
    )
    prompt = BATCH_FILTER_PROMPT.format(
        icp=icp_json, leads_block=leads_block, lead_count=len(chunk)
    )

    try:
        raw_text = await call_llm_raw(prompt)
    except Exception as e:
        if _is_quota_error(e):
            logger.warning("filter_agent: Gemini quota exhausted on batch call, stopping")
            return [], True
        logger.warning(f"filter_agent: batch call failed ({e}), falling back to per-lead")
        raw_text = None

    result = _extract_json(raw_text) if raw_text else None

    if isinstance(result, list) and len(result) == len(chunk):
        kept = []
        for lead, verdict in zip(chunk, result):
            if isinstance(verdict, dict) and verdict.get("is_potential_fit") is True:
                kept.append(lead)
        return kept, False

    # Full parse failed — salvage whatever leading objects are well-formed
    # (covers truncation) before falling back per-lead for the remainder.
    partial = _extract_partial_array(raw_text) if raw_text else []
    covered = min(len(partial), len(chunk))
    if covered:
        logger.warning(
            f"filter_agent: batch response only covered {covered}/{len(chunk)} leads "
            "(truncated or malformed) — recovered the parseable prefix"
        )
    elif raw_text is not None:
        logger.warning(
            f"filter_agent: batch response unusable, 0/{len(chunk)} leads recovered — "
            "falling back to per-lead for the whole chunk"
        )

    kept = []
    for lead, verdict in zip(chunk[:covered], partial[:covered]):
        if isinstance(verdict, dict) and verdict.get("is_potential_fit") is True:
            kept.append(lead)

    for lead in chunk[covered:]:
        is_fit, quota_exhausted = await _filter_lead_individually(lead, icp_json)
        if quota_exhausted:
            return kept, True
        if is_fit:
            kept.append(lead)
    return kept, False


async def run(state: dict) -> dict:
    """Read state['raw_leads'] and state['icp']; classify leads in batches of
    BATCH_SIZE and keep only leads where is_potential_fit == True. Sets
    state['filtered_leads'], and state['error'] if Gemini quota ran out
    partway through (so the pipeline doesn't silently report success).
    """
    try:
        raw_leads = state.get("raw_leads", []) or []
        icp = state.get("icp", {}) or {}
        icp_json = json.dumps(icp)

        filtered_leads = []
        quota_exhausted = False
        for start in range(0, len(raw_leads), BATCH_SIZE):
            chunk = raw_leads[start : start + BATCH_SIZE]
            kept, quota_exhausted = await _filter_chunk(chunk, icp_json)
            filtered_leads.extend(kept)
            if quota_exhausted:
                break

        dropped = len(raw_leads) - len(filtered_leads)
        state["filtered_leads"] = filtered_leads
        if quota_exhausted:
            state["error"] = (
                "Gemini API quota exhausted during lead filtering — "
                f"only {len(filtered_leads)}/{len(raw_leads)} leads were classified "
                "before the run stopped. Wait for the daily quota to reset, or use a "
                "paid API key."
            )
            logger.error(f"filter_agent: stopped early — {state['error']}")
        logger.info(
            f"filter_agent: kept {len(filtered_leads)}/{len(raw_leads)} leads "
            f"(dropped {dropped})"
        )
        return state
    except Exception as e:
        logger.error(f"filter_agent failed: {e}")
        return state
