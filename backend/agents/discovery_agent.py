"""Searches the web for companies matching the structured ICP."""

from backend.tools import serper_search, tavily_search
from backend.utils.logger import logger


def _build_queries(icp: dict) -> list[str]:
    """Build 3 distinct search queries from the structured ICP's keywords."""
    industry = icp.get("industry", "") or ""
    location = icp.get("location", "") or ""
    size_range = icp.get("size_range", "") or ""
    focus = icp.get("focus", "") or ""
    keywords = [k for k in (icp.get("keywords_to_search") or []) if k]

    base = " ".join(filter(None, [industry, "companies", "in", location])).strip()

    queries = []
    if keywords:
        queries.append(f"{base} {keywords[0]}".strip())
    else:
        queries.append(base)

    if len(keywords) > 1:
        queries.append(f"{base} {keywords[1]}".strip())
    elif focus:
        queries.append(f"{base} {focus}".strip())
    else:
        queries.append(f"top {base}".strip())

    if len(keywords) > 2:
        queries.append(f"{base} {keywords[2]}".strip())
    elif size_range:
        queries.append(f"{base} {size_range} employees".strip())
    else:
        queries.append(f"best {base}".strip())

    return [q for q in queries if q]


async def run(state: dict) -> dict:
    """Read state['icp'], search Tavily (falling back to Serper) across 3
    ICP-derived queries, deduplicate by URL, and set state['raw_leads'].
    """
    try:
        icp = state.get("icp", {}) or {}
        queries = _build_queries(icp)
        logger.info(f"discovery_agent: running {len(queries)} search queries")

        seen_urls: set[str] = set()
        raw_leads: list[dict] = []

        for q in queries:
            try:
                results = tavily_search.search(q, max_results=10)
                if not results:
                    logger.warning(f"discovery_agent: Tavily empty for '{q}', trying Serper")
                    results = serper_search.search(q, max_results=10)
            except Exception as e:
                logger.warning(f"discovery_agent: Tavily failed for '{q}' ({e}), trying Serper")
                results = serper_search.search(q, max_results=10)

            for r in results:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                raw_leads.append(
                    {
                        "company_name": r.get("title", "").strip() or url,
                        "url": url,
                        "snippet": r.get("snippet", ""),
                    }
                )

        state["raw_leads"] = raw_leads
        logger.info(f"discovery_agent: found {len(raw_leads)} deduplicated raw leads")
        return state
    except Exception as e:
        logger.error(f"discovery_agent failed: {e}")
        return state
