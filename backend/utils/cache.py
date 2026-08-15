import json

import redis

from backend.config.settings import settings
from backend.utils.logger import logger

try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL or "redis://localhost:6379",
        socket_connect_timeout=2,
        socket_timeout=2,
    )
except Exception as e:
    logger.warning(f"Could not initialise Redis client: {e}")
    redis_client = None


def get_cache(key: str):
    """Return the cached value for `key`, or None on a cache miss / any
    Redis failure (server down, timeout, etc). Never raises."""
    if not redis_client:
        return None
    try:
        val = redis_client.get(key)
        if val:
            return json.loads(val)
        return None
    except Exception as e:
        logger.warning(f"Redis GET failed for key '{key}': {e}")
        return None


def set_cache(key: str, value, ttl: int = 86400):
    """Cache `value` under `key` with the given TTL (seconds). Silently
    no-ops on any Redis failure so callers never have to guard against it."""
    if not redis_client:
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning(f"Redis SET failed for key '{key}': {e}")
