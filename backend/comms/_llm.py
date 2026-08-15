"""
Shared Claude client for the comms layer. Reused by response_classifier.py,
followup_scheduler.py, and (later) meeting_manager.py's briefing generator.

Model: claude-sonnet-4-6 (per root CLAUDE.md).

Two model-specific constraints shape this module:
  - output_config.format (structured outputs) is NOT supported on
    claude-sonnet-4-6, and assistant-turn prefill (the other common way to
    force JSON output) returns a 400 on this model. So we ask for JSON in
    the system prompt and parse defensively instead of relying on either
    API-level guarantee.
  - Classification / short-form generation is not a reasoning-heavy task,
    so thinking is disabled and effort is set to "low" for latency + cost.
    `effort` is GA on Sonnet 4.6 (no beta header needed).

When ANTHROPIC_API_KEY is not set, complete_json() runs in mock mode: it
returns a plausible fake response instead of raising, driven by a small
keyword heuristic supplied by the caller. This keeps test_comms.py runnable
with zero API keys configured.
"""

import json
import re
from typing import Any, Callable, Optional

from comms._deps import get_logger, settings

_log = get_logger("comms.llm")

MODEL = "claude-sonnet-4-6"

_client = None
_client_checked = False


def _get_client():
    """Lazily construct the AsyncAnthropic client. Returns None in mock mode."""
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if not settings.ANTHROPIC_API_KEY:
        _log.warning("ANTHROPIC_API_KEY not set - comms LLM calls running in MOCK MODE")
        return None
    try:
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    except ImportError:
        _log.warning("anthropic package not installed - comms LLM calls running in MOCK MODE")
        _client = None
    return _client


def is_mock_mode() -> bool:
    return _get_client() is None


def _extract_json(text: str) -> dict:
    """
    Defensive JSON extraction. Since sonnet-4-6 supports neither structured
    outputs nor assistant prefill, the model's response is plain text that
    is *supposed* to be pure JSON but may include stray whitespace, markdown
    fences, or (rarely) a leading sentence. Try straightforward parsing
    first, then fall back to grabbing the outermost {...} span.
    """
    text = text.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    _log.error("Failed to parse JSON from model response: %r", text[:500])
    return {}


async def complete_json(
    system: str,
    user: str,
    max_tokens: int = 1024,
    mock_fallback: Optional[Callable[[], dict]] = None,
) -> dict:
    """
    Send a system+user prompt to Claude and parse the response as JSON.

    Returns {} if the model call fails or the response can't be parsed as
    JSON — callers must handle the empty-dict case rather than assume a
    shape, since we have no structured-output guarantee on this model.

    In mock mode (no API key / no anthropic package), calls mock_fallback()
    if provided, else returns {}.
    """
    client = _get_client()

    if client is None:
        if mock_fallback is not None:
            return mock_fallback()
        return {}

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # noqa: BLE001 — comms layer must not crash the pipeline
        _log.error("Claude API call failed: %s", exc)
        if mock_fallback is not None:
            return mock_fallback()
        return {}

    text = next((block.text for block in response.content if block.type == "text"), "")
    return _extract_json(text)
