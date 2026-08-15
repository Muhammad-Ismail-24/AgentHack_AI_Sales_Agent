"""Cheap first-pass filtering — drops obvious non-fits before expensive research."""

import json

from agents.llm_utils import call_llm_json
from config.prompts import FILTER_PROMPT
from utils.logger import logger


async def run(state: dict) -> dict:
    """Read state['raw_leads'] and state['icp']; for each lead, call the LLM
    with FILTER_PROMPT and keep only leads where is_potential_fit == True.
    Sets state['filtered_leads'].
    """
    try:
        raw_leads = state.get("raw_leads", []) or []
        icp = state.get("icp", {}) or {}
        icp_json = json.dumps(icp)

        filtered_leads = []
        for lead in raw_leads:
            try:
                prompt = FILTER_PROMPT.format(
                    company_name=lead.get("company_name", ""),
                    snippet=lead.get("snippet", ""),
                    icp=icp_json,
                )
                result = await call_llm_json(prompt)
                if isinstance(result, dict) and result.get("is_potential_fit") is True:
                    filtered_leads.append(lead)
            except Exception as e:
                logger.warning(
                    f"filter_agent: failed to filter lead "
                    f"'{lead.get('company_name', '?')}': {e}"
                )

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
