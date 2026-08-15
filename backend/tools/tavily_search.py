"""Web search via Tavily — used by discovery_agent to find ICP-matching companies."""

from tavily import TavilyClient

from config.settings import settings
from utils.logger import logger
from utils.rate_limiter import SyncTokenBucket

_bucket = SyncTokenBucket(settings.TAVILY_RPM)


def search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web via Tavily.

    Returns a list of {title, url, snippet} dicts. Returns [] on any failure
    (missing key, network error, rate limit) so callers never have to
    special-case Tavily being unavailable.

    Synchronous and throttled with a blocking wait (SyncTokenBucket) — always
    call this via asyncio.to_thread(...), never directly from a coroutine
    running on the event loop, or a throttled wait freezes the whole server.
    discovery_agent.py already does this.
    """
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set — skipping Tavily search")
        return []

    try:
        _bucket.acquire()
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {e}")
        return []
