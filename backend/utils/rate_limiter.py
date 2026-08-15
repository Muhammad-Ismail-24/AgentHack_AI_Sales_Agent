"""Token-bucket rate limiters shared by every outbound API integration.

Continuous refill + burst tolerance, instead of a hard sliding-window reset:
tokens regenerate at `rate_per_minute / 60` per second up to `capacity`, and
a caller either takes one immediately or waits exactly as long as the next
token needs to arrive.

Two variants, because the concurrency primitives aren't interchangeable:

  - `TokenBucket` — asyncio.Lock + asyncio.sleep. For async call sites
    (agents/llm_utils.py's Gemini calls, comms/whatsapp_notifier.py's Green
    API calls, comms/email_sender.py's Resend calls).
  - `SyncTokenBucket` — threading.Lock + time.sleep. For the plain-`requests`
    tool modules (tavily_search.py, apollo_enrichment.py, hunter_email.py),
    which are synchronous by design and always invoked via
    `asyncio.to_thread(...)` by their callers — blocking inside the executor
    thread is safe; an asyncio.Lock is not (it isn't valid across threads).

Both hold their lock across the wait, not just the refill check — a waiter
sleeps while holding the lock, so concurrent callers queue in order instead
of all waking at once and racing for the same freshly-available token.
"""

import threading
import time
from asyncio import Lock as _AsyncLock
from asyncio import sleep as _asleep


class TokenBucket:
    """Async token bucket. `await bucket.acquire()` before each request."""

    def __init__(self, rate_per_minute: float, capacity: float | None = None) -> None:
        self._rate = max(rate_per_minute, 0.01) / 60.0  # tokens/sec, never zero (would hang forever)
        self._capacity = capacity if capacity is not None else rate_per_minute
        self._tokens = self._capacity
        self._updated_at = time.monotonic()
        self._lock = _AsyncLock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated_at) * self._rate
                )
                self._updated_at = now

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                wait = (1 - self._tokens) / self._rate
                await _asleep(wait)


class SyncTokenBucket:
    """Thread-safe, blocking token bucket for synchronous tool modules.

    `bucket.acquire()` (no await) before each request. Only ever call this
    from inside `asyncio.to_thread(...)` — calling it directly from a
    coroutine running on the event loop would freeze the whole server for
    the duration of any wait.
    """

    def __init__(self, rate_per_minute: float, capacity: float | None = None) -> None:
        self._rate = max(rate_per_minute, 0.01) / 60.0
        self._capacity = capacity if capacity is not None else rate_per_minute
        self._tokens = self._capacity
        self._updated_at = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated_at) * self._rate
                )
                self._updated_at = now

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                wait = (1 - self._tokens) / self._rate
                time.sleep(wait)
