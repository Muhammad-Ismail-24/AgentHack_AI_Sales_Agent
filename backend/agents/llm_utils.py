"""Shared helpers for calling the LLM and parsing its JSON responses.

Not one of the 9 pipeline nodes — a small internal utility used by all of
them so each agent doesn't reimplement "call the LLM, then robustly parse
the JSON out of the response". Prompts still live only in config/prompts.py;
this file just wires up the model client and response parsing.

LLM provider: Google Gemini, over its REST API via httpx.

Why not langchain's ChatGoogleGenerativeAI: langchain-google-genai builds its
own tenacity retry decorator inside `_achat_with_retry` with the retry count
hardcoded, so the `max_retries=0` we passed to the constructor was ignored and
every 429 was silently re-sent ~2s later. Those hidden re-sends never passed
through the limiter below and doubled the quota burn on exactly the calls that
were already failing for lack of quota. Talking to the REST endpoint directly
means the only retry policy is the one written here. (langchain-google-genai
is still a dependency — rag/embedder.py uses its embeddings class.)

Rate limiting: the free-tier Gemini key allows 15 requests/minute, shared by
every agent AND the comms classifier/follow-up/briefing calls — all of which
funnel through call_llm_raw() below. A sliding-window limiter here holds each
call until a slot is free (GEMINI_RPM, default 14 for headroom), so no matter
how many agents or concurrent runs want the model, the key never exceeds its
budget. A 429 that still slips through (another process on the same key, or
the daily cap) waits out the server-suggested delay up to GEMINI_429_RETRIES
times, then raises GeminiQuotaExhausted rather than burning further requests.
"""

import asyncio
import json
import re
import time
from collections import deque

import httpx

from config.settings import settings
from utils.logger import logger

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiQuotaExhausted(RuntimeError):
    """Raised when the Gemini key is out of quota and waiting won't help.

    The message deliberately contains "429" and "quota" so existing checks
    (e.g. filter_agent._is_quota_error) recognise it without changes.
    """


_model_name: str | None = None
_client: httpx.AsyncClient | None = None

# ── Sliding-window RPM limiter ───────────────────────────────────────
# Timestamps of the last requests, oldest first. Guarded by _limiter_lock;
# a waiter holds the lock while sleeping, which also serialises bursts so
# concurrent agents queue fairly instead of stampeding the window.
_call_times: deque[float] = deque()
_limiter_lock = asyncio.Lock()
_WINDOW_SECONDS = 60.0


async def _acquire_slot() -> None:
    """Block until sending one more request keeps us inside GEMINI_RPM."""
    async with _limiter_lock:
        while True:
            now = time.monotonic()
            while _call_times and now - _call_times[0] >= _WINDOW_SECONDS:
                _call_times.popleft()

            if len(_call_times) < max(1, settings.GEMINI_RPM):
                _call_times.append(now)
                return

            wait = _WINDOW_SECONDS - (now - _call_times[0]) + 0.1
            logger.info(
                "Gemini RPM budget full (%d calls in the last 60s) — waiting %.1fs",
                len(_call_times), wait,
            )
            await asyncio.sleep(wait)


def _suggested_retry_seconds(text: str) -> float | None:
    """Pull the server-suggested delay out of a 429 body, if it names one."""
    match = re.search(r"retry(?:_?delay|\s+in)\D*?(\d+(?:\.\d+)?)", text, re.I)
    return float(match.group(1)) if match else None


def _get_client() -> httpx.AsyncClient:
    """One pooled client for the process. httpx does not retry on its own."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    return _client


def _current_model() -> str:
    global _model_name
    if _model_name is None:
        _model_name = settings.GEMINI_MODEL
    return _model_name


def _switch_to_fallback() -> str | None:
    """Swap to the fallback model after a 404.

    Google retires named Gemini models on a rolling basis, and a retired
    model turns every agent call into a 404. Rather than fail the whole run,
    move to the `-latest` alias once and keep going. Returns None when there
    is nothing left to fall back to, which makes the caller surface the 404.
    """
    global _model_name
    fallback = settings.GEMINI_FALLBACK_MODEL
    if not fallback or _model_name == fallback:
        return None

    logger.warning(
        "Gemini model %r unavailable — falling back to %r. "
        "Update GEMINI_MODEL in .env to silence this.",
        _model_name, fallback,
    )
    _model_name = fallback
    return fallback


async def _generate(model: str, prompt: str) -> httpx.Response:
    """One POST to generateContent. No retries — the caller owns that."""
    # The name may or may not already carry the "models/" prefix.
    bare = model[len("models/"):] if model.startswith("models/") else model
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": settings.GEMINI_MAX_TOKENS,
        },
    }
    return await _get_client().post(
        _ENDPOINT.format(model=bare),
        # Header rather than ?key= so the key never lands in a URL or log line.
        headers={
            "x-goog-api-key": settings.google_api_key,
            "Content-Type": "application/json",
        },
        json=payload,
    )


def _response_text(data: dict) -> str:
    """Join the text parts out of a generateContent response."""
    candidates = data.get("candidates") or []
    if not candidates:
        # Usually a safety block — promptFeedback says which filter tripped.
        logger.error(
            "Gemini returned no candidates (promptFeedback=%s)",
            data.get("promptFeedback"),
        )
        return ""

    candidate = candidates[0] or {}
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))

    finish = candidate.get("finishReason")
    if finish == "MAX_TOKENS":
        # Not fatal: callers like filter_agent salvage a truncated JSON array.
        logger.warning(
            "Gemini hit maxOutputTokens (%s) — response is truncated",
            settings.GEMINI_MAX_TOKENS,
        )
    elif finish and finish != "STOP":
        logger.warning("Gemini stopped early (finishReason=%s)", finish)

    return text


def extract_json(text: str) -> dict | list | None:
    """Pull a JSON object/array out of an LLM response.

    Gemini sometimes wraps JSON in ```json ... ``` fences or adds a little
    surrounding prose despite instructions. This tries a straight parse
    first, then falls back to extracting the outermost {...} or [...].
    """
    if not text:
        return None

    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"[\{\[][\s\S]*[\}\]]", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not extract JSON from LLM response: {text[:300]}")
    return None


async def call_llm_raw(prompt: str) -> str:
    """Send `prompt` to Gemini and return the raw text response.

    Split out from call_llm_json so callers that need to recover a partial
    result from a truncated/malformed response (e.g. filter_agent's batch
    prompt) can inspect the raw text themselves instead of only getting None.

    Every request first takes a slot from the RPM limiter. On a 429 the call
    waits out the server-suggested delay and retries up to GEMINI_429_RETRIES
    times; after that it raises GeminiQuotaExhausted so callers stop spending
    requests that are guaranteed to fail. A retired-model 404 swaps to the
    fallback model once. Nothing else re-sends a request.
    """
    if not settings.google_api_key:
        raise RuntimeError(
            "No Gemini API key configured — set GEMINI_API_KEY (or GOOGLE_API_KEY)."
        )

    quota_retries = max(0, settings.GEMINI_429_RETRIES)
    attempt = 0

    while True:
        await _acquire_slot()
        response = await _generate(_current_model(), prompt)

        if response.status_code == 200:
            return _response_text(response.json())

        body = response.text

        # A retired model reports itself as a 404 / NotFound.
        if response.status_code == 404:
            if _switch_to_fallback() is None:
                raise RuntimeError(f"Gemini model not found: {body[:300]}")
            continue

        if response.status_code == 429:
            if attempt >= quota_retries:
                raise GeminiQuotaExhausted(
                    "Gemini API quota exhausted (429) after "
                    f"{attempt + 1} attempt(s). The free tier allows "
                    f"{settings.GEMINI_RPM}/min — if this persists, the "
                    "daily cap is likely spent."
                )
            delay = _suggested_retry_seconds(body) or 20.0
            attempt += 1
            logger.warning(
                "Gemini 429 — waiting %.0fs then retrying (%d/%d)",
                delay, attempt, quota_retries,
            )
            await asyncio.sleep(delay)
            continue

        raise RuntimeError(f"Gemini API error {response.status_code}: {body[:300]}")


async def call_llm_json(prompt: str) -> dict | list | None:
    """Send `prompt` to the LLM and return the parsed JSON response, or None."""
    content = await call_llm_raw(prompt)
    return extract_json(content)
