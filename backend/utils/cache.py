"""Redis helpers. Used for the pipeline's short-term memory and for caching
expensive external calls (scrapes, search results) so reruns are cheap.

Redis is optional: if it is unreachable the helpers degrade to an in-process
dict so a demo still runs on a laptop with no Redis container.
"""

import json
from typing import Any

from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)

try:  # redis is optional at import time
    import redis as _redis_lib
except ImportError:  # pragma: no cover
    _redis_lib = None

_client: Any = None
_fallback: dict[str, str] = {}
_using_fallback = False


def get_client() -> Any:
    """Return a live Redis client, or None when running on the fallback."""
    global _client, _using_fallback

    if _client is not None or _using_fallback:
        return _client

    if _redis_lib is None:
        log.warning("redis package not installed — using in-memory cache")
        _using_fallback = True
        return None

    try:
        # Short timeouts: if Redis isn't up we want the in-memory fallback
        # immediately, not a multi-second stall on the first request.
        client = _redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        _client = client
        log.info("connected to redis at %s", settings.REDIS_URL)
    except Exception as exc:  # noqa: BLE001 - any connection problem falls back
        log.warning("redis unavailable (%s) — using in-memory cache", exc)
        _using_fallback = True

    return _client


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """Store a JSON-serialisable value, optionally with a TTL in seconds."""
    payload = json.dumps(value, default=str)
    client = get_client()
    if client is None:
        _fallback[key] = payload
        return
    if ttl:
        client.setex(key, ttl, payload)
    else:
        client.set(key, payload)


def cache_get(key: str) -> Any | None:
    """Read a value back, or None if the key is missing or unparseable."""
    client = get_client()
    raw = _fallback.get(key) if client is None else client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("cache key %s held non-JSON data — ignoring", key)
        return None


def cache_delete(*keys: str) -> None:
    """Delete one or more keys. Missing keys are ignored."""
    client = get_client()
    if client is None:
        for key in keys:
            _fallback.pop(key, None)
        return
    if keys:
        client.delete(*keys)


def cache_exists(key: str) -> bool:
    client = get_client()
    if client is None:
        return key in _fallback
    return bool(client.exists(key))
