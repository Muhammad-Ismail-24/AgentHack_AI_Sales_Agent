"""Web search via Serper — fallback used when Tavily fails or rate-limits."""

import requests

from config.settings import settings
from utils.logger import logger

SERPER_URL = "https://google.serper.dev/search"


def search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web via Serper (Google Search API).

    Returns a list of {title, url, snippet} dicts — same shape as
    tavily_search.search() so callers can use either interchangeably.
    Returns [] on any failure.
    """
    if not settings.SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set — skipping Serper search")
        return []

    try:
        response = requests.post(
            SERPER_URL,
            headers={
                "X-API-KEY": settings.SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": max_results},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        organic = data.get("organic", [])[:max_results]
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in organic
        ]
    except Exception as e:
        logger.error(f"Serper search failed for query '{query}': {e}")
        return []
