"""Cheap first-pass filtering — drops obvious non-fits before expensive research.

Classifies leads in batches (one LLM call per BATCH_SIZE leads) instead of one
call per lead — a raw_leads list of ~30 used to cost ~30 calls here alone,
which is most of a Gemini free-tier daily quota on its own. Falls back to the
old per-lead prompt only for a chunk whose batched response doesn't parse
cleanly, so a single malformed response can't take out the whole run.
"""

import json

from agents.llm_utils import call_llm_json
from config.prompts import BATCH_FILTER_PROMPT, FILTER_PROMPT
from utils.logger import logger

BATCH_SIZE = 10


async def _filter_lead_individually(lead: dict, icp_json: str) -> bool:
    """One-call-per-lead fallback, used only when a batch response is unusable."""
    try:
        prompt = FILTER_PROMPT.format(
            company_name=lead.get("company_name", ""),
            snippet=lead.get("snippet", ""),
            icp=icp_json,
        )
        result = await call_llm_json(prompt)
        return isinstance(result, dict) and result.get("is_potential_fit") is True
    except Exception as e:
        logger.warning(
            f"filter_agent: failed to filter lead "
            f"'{lead.get('company_name', '?')}': {e}"
        )
        return False


async def _filter_chunk(chunk: list[dict], icp_json: str) -> list[dict]:
    """Classify one chunk of leads with a single LLM call.

    Falls back to per-lead calls for this chunk only if the batched response
    doesn't come back as a same-length JSON array.
    """
    leads_block = "\n".join(
        f"{i}. {lead.get('company_name', '?')} — {lead.get('snippet', '')}"
        for i, lead in enumerate(chunk, start=1)
    )
    prompt = BATCH_FILTER_PROMPT.format(
        icp=icp_json, leads_block=leads_block, lead_count=len(chunk)
    )

    try:
        result = await call_llm_json(prompt)
    except Exception as e:
        logger.warning(f"filter_agent: batch call failed ({e}), falling back to per-lead")
        result = None

    if not isinstance(result, list) or len(result) != len(chunk):
        logger.warning(
            f"filter_agent: batch response unusable "
            f"(got {type(result).__name__}, expected list of {len(chunk)}) — "
            "falling back to per-lead calls for this chunk"
        )
        kept = []
        for lead in chunk:
            if await _filter_lead_individually(lead, icp_json):
                kept.append(lead)
        return kept

    kept = []
    for lead, verdict in zip(chunk, result):
        if isinstance(verdict, dict) and verdict.get("is_potential_fit") is True:
            kept.append(lead)
    return kept


async def run(state: dict) -> dict:
    """Read state['raw_leads'] and state['icp']; classify leads in batches of
    BATCH_SIZE and keep only leads where is_potential_fit == True. Sets
    state['filtered_leads'].
    """
    try:
        raw_leads = state.get("raw_leads", []) or []
        icp = state.get("icp", {}) or {}
        icp_json = json.dumps(icp)

        filtered_leads = []
        for start in range(0, len(raw_leads), BATCH_SIZE):
            chunk = raw_leads[start : start + BATCH_SIZE]
            filtered_leads.extend(await _filter_chunk(chunk, icp_json))

        dropped = len(raw_leads) - len(filtered_leads)
        state["filtered_leads"] = filtered_leads
        logger.info(
            f"filter_agent: kept {len(filtered_leads)}/{len(raw_leads)} leads "
            f"(dropped {dropped})"
        )
        return state
    except Exception as e:
        logger.error(f"filter_agent failed: {e}")
        return state
