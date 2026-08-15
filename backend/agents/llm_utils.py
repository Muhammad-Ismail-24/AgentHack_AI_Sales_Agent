"""Shared helpers for calling the LLM and parsing its JSON responses.

Not one of the 9 pipeline nodes — a small internal utility used by all of
them so each agent doesn't reimplement "call the LLM, then robustly parse
the JSON out of the response". Prompts still live only in config/prompts.py;
this file just wires up the model client and response parsing.

LLM provider: Google Gemini, via langchain-google-genai.

Rate limiting: the free-tier Gemini key allows 15 requests/minute, shared by
every agent AND the comms classifier/follow-up/briefing calls — all of which
funnel through call_llm_raw() below. A module-level TokenBucket (GEMINI_RPM,
default 14 for headroom) throttles every call before it's sent, so no matter
how many agents or concurrent pipeline runs want the model, the key never
exceeds its budget. A 429 that still slips through (another process on the
same key, daily cap) waits out the server-suggested delay once, then raises
GeminiQuotaExhausted rather than burning further requests on retries.
"""

import asyncio
import json
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from utils.logger import logger
from utils.rate_limiter import TokenBucket


class GeminiQuotaExhausted(RuntimeError):
    """Raised when the Gemini key is out of quota and waiting won't help.

    The message deliberately contains "429" and "quota" so existing checks
    (e.g. filter_agent._is_quota_error) recognise it without changes.
    """


_llm: ChatGoogleGenerativeAI | None = None
_model_name: str | None = None

_gemini_bucket = TokenBucket(settings.GEMINI_RPM)


def is_quota_error(exc: BaseException) -> bool:
    text = str(exc)
    return (
        "429" in text
        or "ResourceExhausted" in type(exc).__name__
        or "quota" in text.lower()
    )


def _suggested_retry_seconds(exc: BaseException) -> float | None:
    """Pull the server-suggested delay out of a 429, if it names one."""
    match = re.search(r"retry(?:_delay|\s+in)\D*?(\d+(?:\.\d+)?)", str(exc), re.I)
    return float(match.group(1)) if match else None


def _build(model: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.google_api_key,
        max_output_tokens=settings.GEMINI_MAX_TOKENS,
        temperature=0.2,
        timeout=60,
        # No client-internal retries: langchain's default (6, exponential
        # backoff) re-sends failed calls invisibly, and each re-send counts
        # against the 15 RPM budget without passing through our limiter.
        # Retry policy lives in call_llm_raw where it can be accounted for.
        max_retries=0,
    )


def get_llm() -> ChatGoogleGenerativeAI:
    """Return a shared ChatGoogleGenerativeAI client configured from settings."""
    global _llm, _model_name
    if _llm is None:
        _model_name = settings.GEMINI_MODEL
        _llm = _build(_model_name)
    return _llm


def _switch_to_fallback() -> ChatGoogleGenerativeAI | None:
    """Swap to the fallback model after a 404.

    Google retires named Gemini models on a rolling basis, and a retired
    model turns every agent call into a 404. Rather than fail the whole run,
    move to the `-latest` alias once and keep going.
    """
    global _llm, _model_name
    fallback = settings.GEMINI_FALLBACK_MODEL
    if not fallback or _model_name == fallback:
        return None

    logger.warning(
        "Gemini model %r unavailable — falling back to %r. "
        "Update GEMINI_MODEL in .env to silence this.",
        _model_name, fallback,
    )
    _model_name = fallback
    _llm = _build(fallback)
    return _llm


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


def extract_partial_array(text: str) -> list[dict]:
    """Recover as many leading objects as possible from a truncated JSON array.

    Scans for top-level {...} blocks in order and stops at the first one that
    doesn't parse — which is exactly where a max-tokens cutoff lands, since
    everything before the cut is still well-formed JSON. Shared by every
    batched-array agent (filter_agent, combined_processing_agent, ...) so a
    truncated batch response only loses the unparsed tail, not the whole call.
    """
    if not text:
        return []

    objects: list[dict] = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    break
                if not isinstance(obj, dict):
                    break
                objects.append(obj)
                start = None
    return objects


async def call_llm_raw(prompt: str) -> str:
    """Send `prompt` to the LLM and return the raw text response.

    Split out from call_llm_json so callers that need to recover a partial
    result from a truncated/malformed response (e.g. filter_agent's batch
    prompt) can inspect the raw text themselves instead of only getting None.

    Every request first takes a slot from the RPM limiter. On a 429 the call
    waits out the server-suggested delay and retries up to GEMINI_429_RETRIES
    times; after that it raises GeminiQuotaExhausted so callers stop spending
    requests that are guaranteed to fail. A retired-model 404 swaps to the
    fallback model once.
    """
    messages = [HumanMessage(content=prompt)]

    quota_retries = max(0, settings.GEMINI_429_RETRIES)
    attempt = 0
    while True:
        await _gemini_bucket.acquire()
        try:
            response = await get_llm().ainvoke(messages)
            break
        except Exception as exc:  # noqa: BLE001
            text = str(exc)

            # A retired model reports itself as a 404 / NotFound.
            if "404" in text or "not found" in text.lower():
                fallback = _switch_to_fallback()
                if fallback is None:
                    raise
                await _gemini_bucket.acquire()
                response = await fallback.ainvoke(messages)
                break

            if is_quota_error(exc):
                if attempt >= quota_retries:
                    raise GeminiQuotaExhausted(
                        "Gemini API quota exhausted (429) after "
                        f"{attempt + 1} attempt(s). The free tier allows "
                        f"{settings.GEMINI_RPM}/min — if this persists, the "
                        "daily cap is likely spent."
                    ) from exc
                delay = _suggested_retry_seconds(exc) or 20.0
                attempt += 1
                logger.warning(
                    "Gemini 429 — waiting %.0fs then retrying (%d/%d)",
                    delay, attempt, quota_retries,
                )
                await asyncio.sleep(delay)
                continue

            raise

    return (
        response.content
        if isinstance(response.content, str)
        else str(response.content)
    )


async def call_llm_json(prompt: str) -> dict | list | None:
    """Send `prompt` to the LLM and return the parsed JSON response, or None."""
    content = await call_llm_raw(prompt)
    return extract_json(content)
