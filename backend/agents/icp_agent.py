"""Structures the user's raw ICP form answers into a typed ICP object via the LLM."""

from agents.llm_utils import call_llm_json
from config.prompts import ICP_STRUCTURING_PROMPT
from utils.logger import logger


async def run(state: dict) -> dict:
    """Read state['icp_raw'] (location, industry, size, focus), call the LLM
    with ICP_STRUCTURING_PROMPT, and set state['icp'] to the parsed result.
    """
    try:
        icp_raw = state.get("icp_raw", {}) or {}

        prompt = ICP_STRUCTURING_PROMPT.format(
            target_location=icp_raw.get("location", "Anywhere"),
            target_industry=icp_raw.get("industry", "Any industry"),
            company_size=icp_raw.get("size", "Any size"),
            special_focus=icp_raw.get("focus", "General outreach"),
        )

        parsed = await call_llm_json(prompt)
        if not isinstance(parsed, dict):
            logger.error("icp_agent: The LLM did not return a valid ICP JSON object")
            return state

        state["icp"] = parsed
        logger.info(f"icp_agent: structured ICP -> {parsed}")
        return state
    except Exception as e:
        logger.error(f"icp_agent failed: {e}")
        return state
