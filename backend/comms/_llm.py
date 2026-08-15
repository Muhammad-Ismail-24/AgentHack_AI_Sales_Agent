"""Shared LLM client for the comms layer — reply classification, follow-up
drafting, and meeting briefings.

Originally written against Claude. The project runs on Google Gemini (the
agents already do, and the deployed key set is Gemini-only), so this now
delegates to `agents.llm_utils`, which owns the single Gemini client. The
public interface is unchanged: `complete_json(system, user, ...)` still
returns a parsed dict, still never raises, and still falls back to
`mock_fallback()` when no key is configured.

Gemini has no separate "system" role in this path, so the system and user
prompts are concatenated — which is how the agent prompts are already
structured.
"""

from typing import Callable, Optional

from comms._deps import get_logger, settings

_log = get_logger("comms.llm")


def is_mock_mode() -> bool:
    """True when no Gemini key is configured, so callers can skip network work."""
    return not settings.google_api_key


async def complete_json(
    system: str,
    user: str,
    max_tokens: int = 1024,  # noqa: ARG001 - kept for call-site compatibility
    mock_fallback: Optional[Callable[[], dict]] = None,
) -> dict:
    """Send a system+user prompt to Gemini and parse the response as JSON.

    Returns {} if the call fails or the response cannot be parsed — callers
    must handle the empty-dict case rather than assume a shape. In mock mode
    (no API key) calls `mock_fallback()` if given, else returns {}.
    """
    if is_mock_mode():
        _log.warning("no Gemini API key set — comms LLM running in MOCK MODE")
        return mock_fallback() if mock_fallback is not None else {}

    try:
        from agents.llm_utils import call_llm_json
    except ImportError as exc:  # pragma: no cover
        _log.error("agents.llm_utils unavailable (%s)", exc)
        return mock_fallback() if mock_fallback is not None else {}

    prompt = f"{system.strip()}\n\n{user.strip()}" if system else user

    try:
        result = await call_llm_json(prompt)
    except Exception as exc:  # noqa: BLE001 - comms must never crash the pipeline
        _log.error("Gemini call failed: %s", exc)
        return mock_fallback() if mock_fallback is not None else {}

    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0]

    _log.error("LLM returned no usable JSON object")
    return mock_fallback() if mock_fallback is not None else {}
