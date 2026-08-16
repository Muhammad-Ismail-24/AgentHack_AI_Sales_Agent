"""Structures the user's raw ICP form answers into a typed ICP object via the LLM."""

from agents.llm_utils import call_llm_json
from config.prompts import ICP_STRUCTURING_PROMPT
from utils.logger import logger


def _field(icp_raw: dict, *names: str, default: str) -> str:
    """First non-empty value among `names`, else `default`.

    The ICP dict reaches this agent under two spellings: POST /icp/define
    builds it from ICPRequest as `company_size`/`special_focus`, while
    test_pipeline.py uses the shorter `size`/`focus`. Reading only the short
    names meant every run through the API silently structured its ICP against
    "Any size" / "General outreach" — and the test script, using the short
    names, never showed it. Accept both; ICPRequest's names come first.
    """
    for name in names:
        value = icp_raw.get(name)
        if value:
            return str(value)
    return default


async def run(state: dict) -> dict:
    """Read state['icp_raw'] (location, industry, size, focus), call the LLM
    with ICP_STRUCTURING_PROMPT, and set state['icp'] to the parsed result.
    """
    try:
        icp_raw = state.get("icp_raw", {}) or {}

        prompt = ICP_STRUCTURING_PROMPT.format(
            target_location=_field(icp_raw, "location", default="Anywhere"),
            target_industry=_field(icp_raw, "industry", default="Any industry"),
            company_size=_field(icp_raw, "company_size", "size", default="Any size"),
            special_focus=_field(
                icp_raw, "special_focus", "focus", default="General outreach"
            ),
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
