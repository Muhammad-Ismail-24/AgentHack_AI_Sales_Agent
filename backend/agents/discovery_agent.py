"""Searches the web for companies matching the structured ICP.

Two things here exist to keep listicles out of the lead list. Queries used to
be built as "top <industry> companies in <location>" / "best ...", which asks
a search engine for exactly the roundup articles we don't want; each keyword
now becomes its own query instead. And whatever still comes back gets checked
against _is_directory_result, because "Top 35 Logistics Companies in Dubai" is
a page about companies, not a company — sending it downstream wastes a
research pass and an LLM call before the filter rejects it anyway.
"""

import re
from urllib.parse import urlparse

from tools import serper_search, tavily_search
from utils.logger import logger

# Aggregators, directories, jobs boards and social — never a prospect's own site.
_DIRECTORY_DOMAINS = frozenset(
    {
        "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
        "youtube.com", "tiktok.com", "reddit.com", "quora.com", "medium.com",
        "wikipedia.org", "forbes.com", "bloomberg.com", "reuters.com",
        "tradingview.com", "statista.com", "glassdoor.com", "indeed.com",
        "crunchbase.com", "zoominfo.com", "owler.com", "dnb.com", "clutch.co",
        "yelp.com", "yellowpages.com", "tripadvisor.com", "ambitionbox.com",
        "builtin.com", "themuse.com", "comparably.com", "greatplacetowork.com",
        "topworkplaces.com", "trustpilot.com", "g2.com", "capterra.com",
        "expertmarketresearch.com", "mordorintelligence.com", "ibisworld.com",
    }
)

# Titles that describe a roundup of companies rather than naming one.
_LISTICLE_PATTERNS = (
    r"\btop\s+\d+\b",
    r"\bbest\s+\d+\b",
    r"\btop\s+\d*\s*(?:best|leading|largest|biggest)\b",
    r"\blist\s+of\b",
    r"\b(?:largest|biggest|leading)\s+\w+\s+compan(?:y|ies)\b",
    r"\bcompanies\s+to\s+work\s+for\b",
    r"\bbest\s+places?\s+to\s+work\b",
    r"\b(?:major|top|largest|biggest|key)\s+employers\b",
    r"\b(?:companies|firms|providers|suppliers)\s+in\s+\w+\s*[:\-–]",
    r"\bdirectory\b",
    r"\branking?s?\b",
    r"\bmarket\s+(?:report|size|share|research)\b",
)


def _registrable_domain(url: str) -> str:
    """Best-effort eTLD+1 so 'www.x.linkedin.com' matches 'linkedin.com'."""
    try:
        host = (urlparse(url).netloc or "").lower().split(":")[0]
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    # Two labels is right for .com/.ae; three for the .co.uk / .com.sa shapes.
    if len(parts) > 2 and parts[-2] in {"co", "com", "net", "org", "gov", "edu"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_directory_result(title: str, url: str) -> bool:
    """True when a search hit is a roundup/directory rather than a company."""
    domain = _registrable_domain(url)
    if domain in _DIRECTORY_DOMAINS:
        return True

    lowered = (title or "").lower()
    return any(re.search(pattern, lowered) for pattern in _LISTICLE_PATTERNS)


def _build_queries(icp: dict) -> list[str]:
    """Build focused search queries from the structured ICP.

    Each keyword is used as its own query, rather than being concatenated onto
    an industry+location stem — the concatenated form produced long redundant
    strings that search engines answered with roundup articles. ICP keywords
    already carry their own geography (ICP_STRUCTURING_PROMPT asks for phrases
    a search engine could use directly, and they come back looking like
    "freight forwarding companies UAE"), so appending the location again just
    lengthens the query for nothing. Falls back to industry/focus + location
    only when the ICP has no keywords at all.
    """
    industry = icp.get("industry", "") or ""
    location = icp.get("location", "") or ""
    focus = icp.get("focus", "") or ""
    keywords = [k.strip() for k in (icp.get("keywords_to_search") or []) if k and k.strip()]

    queries: list[str] = list(keywords[:3])

    if not queries and (industry or location):
        queries.append(" ".join(filter(None, [industry, "companies", location])).strip())
        if focus:
            queries.append(" ".join(filter(None, [industry, focus, location])).strip())

    # Dedupe while keeping order.
    seen: set[str] = set()
    unique = []
    for q in queries:
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


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
        dropped_directory = 0

        import asyncio
        for q in queries:
            try:
                results = await asyncio.to_thread(tavily_search.search, q, max_results=10)
                if not results:
                    logger.warning(f"discovery_agent: Tavily empty for '{q}', trying Serper")
                    results = await asyncio.to_thread(serper_search.search, q, max_results=10)
            except Exception as e:
                logger.warning(f"discovery_agent: Tavily failed for '{q}' ({e}), trying Serper")
                results = await asyncio.to_thread(serper_search.search, q, max_results=10)

            for r in results:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = (r.get("title") or "").strip()
                if _is_directory_result(title, url):
                    dropped_directory += 1
                    continue

                raw_leads.append(
                    {
                        "company_name": title or url,
                        "url": url,
                        "snippet": r.get("snippet", ""),
                    }
                )

        state["raw_leads"] = raw_leads
        logger.info(
            f"discovery_agent: found {len(raw_leads)} deduplicated raw leads "
            f"(dropped {dropped_directory} directory/listicle results)"
        )
        if not raw_leads and dropped_directory:
            logger.warning(
                "discovery_agent: every result was a directory or roundup page — "
                "the ICP keywords may be too broad to surface individual companies"
            )
        return state
    except Exception as e:
        logger.error(f"discovery_agent failed: {e}")
        return state
