"""Hunter.io domain-search email finder, cached in Redis for 48h per domain."""

import requests

from backend.config.settings import settings
from backend.utils.cache import get_cache, set_cache
from backend.utils.logger import logger

HUNTER_URL = "https://api.hunter.io/v2/domain-search"
CACHE_TTL_SECONDS = 48 * 60 * 60  # 48h


def _cache_key(domain: str) -> str:
    return f"hunter:{domain}"


def find_emails(domain: str) -> list[dict]:
    """Find verified email addresses for decision-makers at a domain.

    Returns a list of {email, first_name, last_name, position, confidence}.
    Returns [] on any failure. Checks Redis first — if the domain was looked
    up in the last 48h, returns the cached result.
    """
    if not domain:
        return []

    cached = get_cache(_cache_key(domain))
    if cached is not None:
        logger.info(f"Cache hit for Hunter lookup: {domain}")
        return cached

    if not settings.HUNTER_API_KEY:
        logger.warning("HUNTER_API_KEY not set — skipping Hunter lookup")
        return []

    try:
        response = requests.get(
            HUNTER_URL,
            params={"domain": domain, "api_key": settings.HUNTER_API_KEY},
            timeout=15,
        )
        response.raise_for_status()
        emails = response.json().get("data", {}).get("emails", [])

        result = [
            {
                "email": e.get("value", ""),
                "first_name": e.get("first_name", ""),
                "last_name": e.get("last_name", ""),
                "position": e.get("position", ""),
                "confidence": e.get("confidence"),
            }
            for e in emails
        ]
        set_cache(_cache_key(domain), result, ttl=CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Hunter lookup failed for domain '{domain}': {e}")
        return []
