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


def _is_searchable(icp: object) -> bool:
    """True when discovery_agent could actually build a query from this ICP.

    Being a dict is not enough. _build_queries works from keywords_to_search,
    falling back to industry + location, so a response like {} or one that
    only carries `focus` yields no queries at all — discovery then searches
    nothing and the run ends `complete` with 0 leads and no error, which is
    the failure this fallback exists to prevent. Treat those as unusable and
    take the form answers instead.
    """
    if not isinstance(icp, dict):
        return False
    if any(str(k).strip() for k in (icp.get("keywords_to_search") or [])):
        return True
    return bool(str(icp.get("industry") or "").strip()
                or str(icp.get("location") or "").strip())


def _fallback_icp(icp_raw: dict) -> dict:
    """The form answers, shaped like ICP_STRUCTURING_PROMPT's output schema.

    Used whenever the LLM cannot structure the ICP. It matters that this is
    never empty: discovery_agent builds its search queries from state['icp']
    alone, and _build_queries({}) returns zero queries — so leaving `icp`
    unset meant discovery ran no searches at all and the whole run finished
    with 0 leads, reported as `complete` with no error. The raw form fields
    are the user's own stated intent and make a perfectly usable query.

    `keywords_to_search` is deliberately empty: _build_queries falls back to
    its industry + location path when there are none, and inventing keywords
    without the LLM is exactly what produced listicle queries before.
    """
    return {
        "location": _field(icp_raw, "location", default=""),
        "industry": _field(icp_raw, "industry", default=""),
        "size_range": _field(icp_raw, "company_size", "size", default=""),
        "focus": _field(icp_raw, "special_focus", "focus", default=""),
        "keywords_to_search": [],
        "structured": False,
    }


async def run(state: dict) -> dict:
    """Read state['icp_raw'] (location, industry, size, focus), call the LLM
    with ICP_STRUCTURING_PROMPT, and set state['icp'] to the parsed result.

    Always sets state['icp'] — on any failure it falls back to the raw form
    answers rather than leaving the key unset. `structured` says which of the
    two happened; this agent is the only writer of that flag.
    """
    icp_raw = state.get("icp_raw", {}) or {}

    try:
        prompt = ICP_STRUCTURING_PROMPT.format(
            target_location=_field(icp_raw, "location", default="Anywhere"),
            target_industry=_field(icp_raw, "industry", default="Any industry"),
            company_size=_field(icp_raw, "company_size", "size", default="Any size"),
            special_focus=_field(
                icp_raw, "special_focus", "focus", default="General outreach"
            ),
        )

        parsed = await call_llm_json(prompt)
        if not _is_searchable(parsed):
            logger.warning(
                "icp_agent: the LLM returned no usable ICP (%r) — falling back "
                "to the raw form answers",
                parsed,
            )
            state["icp"] = _fallback_icp(icp_raw)
            return state

        state["icp"] = {**parsed, "structured": True}
        logger.info(f"icp_agent: structured ICP -> {parsed}")
        return state
    except Exception as e:
        logger.warning(
            f"icp_agent: could not structure the ICP ({e}) — falling back to "
            f"the raw form answers, so discovery still has something to search"
        )
        state["icp"] = _fallback_icp(icp_raw)
        return state
