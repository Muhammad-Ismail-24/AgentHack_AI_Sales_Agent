"""Apollo.io company enrichment, cached in Redis for 48h per domain."""

import requests

from config.settings import settings
from utils.cache import get_cache, set_cache
from utils.logger import logger
from utils.rate_limiter import SyncTokenBucket

APOLLO_URL = "https://api.apollo.io/api/v1/organizations/enrich"
CACHE_TTL_SECONDS = 48 * 60 * 60  # 48h

_bucket = SyncTokenBucket(settings.APOLLO_RPM)


def _cache_key(domain: str) -> str:
    return f"apollo:{domain}"


def enrich_company(domain: str) -> dict:
    """Enrich a company by domain via Apollo.io.

    Returns {name, industry, employee_count, location, founded_year,
    funding_total}. Returns {} on any failure. Checks Redis first — if the
    domain was looked up in the last 48h, returns the cached result.

    Synchronous and throttled with a blocking wait (SyncTokenBucket) — always
    call this via asyncio.to_thread(...), never directly from a coroutine
    running on the event loop, or a throttled wait freezes the whole server.
    research_agent.py already does this.
    """
    if not domain:
        return {}

    cached = get_cache(_cache_key(domain))
    if cached is not None:
        logger.info(f"Cache hit for Apollo enrichment: {domain}")
        return cached

    if not settings.APOLLO_API_KEY:
        logger.warning("APOLLO_API_KEY not set — skipping Apollo enrichment")
        return {}

    try:
        _bucket.acquire()
        response = requests.get(
            APOLLO_URL,
            headers={
                "X-Api-Key": settings.APOLLO_API_KEY,
                "Content-Type": "application/json",
            },
            params={"domain": domain},
            timeout=15,
        )
        response.raise_for_status()
        org = response.json().get("organization") or {}

        result = {
            "name": org.get("name", ""),
            "industry": org.get("industry", ""),
            "employee_count": org.get("estimated_num_employees"),
            "location": ", ".join(
                filter(None, [org.get("city"), org.get("state"), org.get("country")])
            ),
            "founded_year": org.get("founded_year"),
            "funding_total": org.get("total_funding"),
        }
        set_cache(_cache_key(domain), result, ttl=CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Apollo enrichment failed for domain '{domain}': {e}")
        return {}
