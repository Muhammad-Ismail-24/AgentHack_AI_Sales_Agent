"""Groq client — used ONLY by the intelligence layer.

The split is deliberate and is the whole point of this module:

  * `agents/llm_utils.py` (Google Gemini) drives the original pipeline —
    ICP, filter, research, combined processing — and the original comms
    calls: reply classification and follow-up drafting. **Nothing in this
    file touches that path.**
  * this file (Groq) drives the extra-credit features only — Devil's
    Advocate, Deal Autopsy, and the Executive Whisperer script.

Two providers means two quotas. The Gemini free tier caps requests per minute
*and* per day per model, and a Devil's Advocate debate costs three calls;
running debates used to eat budget the pipeline needed. Split across two keys
a demo can hold debates and run the pipeline in the same session without
either starving the other. Groq's inference is also fast enough that a
three-call debate resolves in a couple of seconds, which matters when the
whole thing has to happen on camera.

Transport: Groq's OpenAI-compatible REST API —
POST {GROQ_API_URL}/chat/completions with a `messages` array. Plain httpx,
no SDK, matching how llm_utils and whatsapp_notifier talk to their providers.

Structured output: the request asks for `response_format: json_object`. Groq
requires the word "json" to appear in the prompt when that is set — every
prompt in config/prompts.py already says "Respond with ONLY valid JSON" — and
not every model accepts the parameter at all, so a 400 about it downgrades the
request once, remembers, and falls back to the same tolerant extractor the
Gemini path uses.

Rate limiting and model chaining mirror llm_utils: a sliding-window limiter
holds calls to GROQ_RPM, and a 429 walks along GROQ_MODEL_FALLBACKS before it
resorts to waiting. Groq retires models briskly (a decommissioned model 400s
with `model_decommissioned`), so that chain is doing real work, not being
defensive for its own sake.
"""

import asyncio
import json
import re
import time
from collections import deque

import httpx

# extract_json is a pure text helper with no Gemini state — imported rather
# than duplicated. Nothing here calls, configures, or mutates the Gemini
# client that lives alongside it.
from agents.llm_utils import extract_json
from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)


class GroqQuotaExhausted(RuntimeError):
    """Raised when the Groq key is out of quota and waiting will not help.

    Mirrors GeminiQuotaExhausted, and the message likewise contains "429" and
    "quota" so any caller sniffing for those words behaves the same way.
    """


class GroqUnavailable(RuntimeError):
    """Raised when no GROQ_API_KEY is configured."""


_model_index = 0
_client: httpx.AsyncClient | None = None
# Set False once a model rejects response_format, so later calls skip it.
_json_mode_supported = True

# ── Sliding-window RPM limiter ───────────────────────────────────────
# Separate deque and lock from the Gemini limiter on purpose: two providers,
# two independent budgets. Sharing one would throttle Groq against Gemini's
# much tighter free-tier ceiling for no reason.
_call_times: deque[float] = deque()
_limiter_lock = asyncio.Lock()
_WINDOW_SECONDS = 60.0


async def _acquire_slot() -> None:
    """Block until sending one more request keeps us inside GROQ_RPM."""
    async with _limiter_lock:
        while True:
            now = time.monotonic()
            while _call_times and now - _call_times[0] >= _WINDOW_SECONDS:
                _call_times.popleft()

            if len(_call_times) < max(1, settings.GROQ_RPM):
                _call_times.append(now)
                return

            wait = _WINDOW_SECONDS - (now - _call_times[0]) + 0.1
            log.info(
                "Groq RPM budget full (%d calls in the last 60s) — waiting %.1fs",
                len(_call_times), wait,
            )
            await asyncio.sleep(wait)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """How long Groq asked us to wait — header first, then the body.

    Groq sends a `retry-after` header on 429s and also spells the wait out in
    the error message ("Please try again in 7.5s"), so both are checked.
    """
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass

    match = re.search(r"try again in\s*(\d+(?:\.\d+)?)\s*([ms])", response.text, re.I)
    if match:
        value = float(match.group(1))
        return value * 60 if match.group(2).lower() == "m" else value
    return None


def _get_client() -> httpx.AsyncClient:
    """One pooled client for the process. httpx does not retry on its own."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(90.0))
    return _client


def _current_model() -> str:
    chain = settings.groq_model_chain
    return chain[min(_model_index, len(chain) - 1)] if chain else settings.GROQ_MODEL


def _advance_model(reason: str) -> str | None:
    """Move to the next model in the chain. None when the chain is spent.

    Process-global on purpose, same as the Gemini chain: once a model is known
    bad, every later call should skip it rather than rediscover it one failed
    request at a time.
    """
    global _model_index
    chain = settings.groq_model_chain
    if _model_index >= len(chain) - 1:
        return None

    previous = chain[_model_index]
    _model_index += 1
    nxt = chain[_model_index]
    log.warning(
        "Groq model %r %s — switching to %r (%d of %d in the chain)",
        previous, reason, nxt, _model_index + 1, len(chain),
    )
    return nxt


async def _chat(model: str, prompt: str, json_mode: bool) -> httpx.Response:
    """One POST to /chat/completions. No retries — the caller owns that."""
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": settings.GROQ_MAX_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    return await _get_client().post(
        f"{settings.GROQ_API_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )


def _response_text(data: dict) -> str:
    """Pull the assistant message out of an OpenAI-shaped response."""
    choices = data.get("choices") or []
    if not choices:
        log.error("Groq returned no choices (body keys: %s)", list(data))
        return ""

    choice = choices[0] or {}
    text = ((choice.get("message") or {}).get("content")) or ""

    finish = choice.get("finish_reason")
    if finish == "length":
        # Not fatal — extract_json salvages a truncated object where it can.
        log.warning(
            "Groq hit max_tokens (%s) — response is truncated",
            settings.GROQ_MAX_TOKENS,
        )
    elif finish and finish not in ("stop", "end_turn"):
        log.warning("Groq stopped early (finish_reason=%s)", finish)

    return text


def _is_json_mode_complaint(status: int, body: str) -> bool:
    """True when a 400 is specifically about the response_format parameter.

    Covers both ways Groq refuses it: the model not supporting the parameter,
    and json_object mode rejecting a prompt that never says "json".
    """
    if status != 400:
        return False
    lowered = body.lower()
    return "response_format" in lowered or "json_object" in lowered or (
        "json" in lowered and "must contain" in lowered
    )


def _is_bad_model(status: int, body: str) -> bool:
    """True when the failure is the model name rather than the request."""
    if status == 404:
        return True
    lowered = body.lower()
    return status in (400, 422) and (
        "model_decommissioned" in lowered
        or "does not exist" in lowered
        or "model_not_found" in lowered
        or ("model" in lowered and "decommissioned" in lowered)
    )


async def call_llm_raw(prompt: str) -> str:
    """Send `prompt` to Groq and return the raw text response.

    Every request first takes a slot from the RPM limiter. A 429 walks the
    model chain before waiting, since each model carries its own budget. Once
    the chain is spent it waits out the server-suggested delay up to
    GROQ_429_RETRIES times, then raises GroqQuotaExhausted so callers stop
    spending requests that are guaranteed to fail.
    """
    global _json_mode_supported

    if not settings.GROQ_API_KEY:
        raise GroqUnavailable(
            "No Groq API key configured — set GROQ_API_KEY. The intelligence "
            "layer (Devil's Advocate, Deal Autopsy, Executive Whisperer) runs "
            "on Groq; the rest of the pipeline is unaffected and still uses "
            "Gemini."
        )

    quota_retries = max(0, settings.GROQ_429_RETRIES)
    attempt = 0

    while True:
        await _acquire_slot()
        response = await _chat(_current_model(), prompt, _json_mode_supported)

        if response.status_code == 200:
            return _response_text(response.json())

        body = response.text

        # The model will not take response_format — drop it and retry once.
        # Remembered process-wide so this costs one request, not one per call.
        if _json_mode_supported and _is_json_mode_complaint(response.status_code, body):
            _json_mode_supported = False
            log.warning(
                "Groq model %r rejected response_format=json_object — retrying "
                "without it and parsing the JSON out of the text instead",
                _current_model(),
            )
            continue

        # A retired or misspelled model name.
        if _is_bad_model(response.status_code, body):
            if _advance_model("is unavailable or decommissioned") is None:
                raise RuntimeError(
                    f"Groq model not found: {body[:300]}. Check the names in "
                    "GROQ_MODEL / GROQ_MODEL_FALLBACKS against the current "
                    "list at https://console.groq.com/docs/models"
                )
            continue

        if response.status_code == 429:
            if _advance_model("is rate limited or out of quota") is not None:
                continue

            if attempt >= quota_retries:
                raise GroqQuotaExhausted(
                    "Groq API quota exhausted (429) on every model in the "
                    f"chain ({', '.join(settings.groq_model_chain)}) after "
                    f"{attempt + 1} attempt(s). The free tier caps requests "
                    "and tokens per minute as well as per day."
                )
            delay = _retry_after_seconds(response) or 20.0
            attempt += 1
            log.warning(
                "Groq 429 on the last model in the chain — waiting %.0fs then "
                "retrying (%d/%d)",
                delay, attempt, quota_retries,
            )
            await asyncio.sleep(delay)
            continue

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Groq rejected the API key ({response.status_code}). Check "
                f"GROQ_API_KEY — it should start with 'gsk_'. "
                f"Response: {body[:200]}"
            )

        raise RuntimeError(f"Groq API error {response.status_code}: {body[:300]}")


async def call_llm_json(prompt: str) -> dict | list | None:
    """Send `prompt` to Groq and return the parsed JSON response, or None."""
    content = await call_llm_raw(prompt)
    if not content:
        return None

    # json_object mode usually makes this a straight parse; the tolerant
    # extractor covers the downgraded path where fences or prose creep in.
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return extract_json(content)


def is_available() -> bool:
    """True when a Groq call could actually be attempted."""
    return bool(settings.GROQ_API_KEY)
