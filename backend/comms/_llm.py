"""Shared LLM clients for the comms layer.

Two entry points, one per provider, because the project deliberately splits
its LLM traffic:

  * `complete_json()` → **Gemini**, via `agents.llm_utils`. Drives the
    original comms features — reply classification and follow-up drafting.
    Unchanged.
  * `complete_json_groq()` → **Groq**, via `agents.groq_utils`. Drives the
    Executive Whisperer pre-call script only.

Same signature, same contract on both: a parsed dict, never raises, and
`mock_fallback()` when that provider's key is missing. A caller picks its
provider by picking its function, so adding the second one changed nothing
about the first.

Neither provider path uses a separate "system" role here — the system and
user prompts are concatenated, which is how the agent prompts are already
structured.
"""

from typing import Callable, Optional

from comms._deps import get_logger, settings

_log = get_logger("comms.llm")


def is_mock_mode() -> bool:
    """True when no Gemini key is configured, so callers can skip network work."""
    return not settings.google_api_key


def is_groq_mock_mode() -> bool:
    """True when no Groq key is configured."""
    return not settings.GROQ_API_KEY


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


async def complete_json_groq(
    system: str,
    user: str,
    max_tokens: int = 1024,  # noqa: ARG001 - kept for call-site symmetry
    mock_fallback: Optional[Callable[[], dict]] = None,
) -> dict:
    """Same contract as `complete_json`, but against Groq instead of Gemini.

    Used by the Executive Whisperer only. Deliberately a separate function
    rather than a provider argument on `complete_json`: the reply classifier
    and follow-up writer must keep reaching Gemini no matter what happens
    here, and a shared code path is exactly how that guarantee gets lost.
    """
    if is_groq_mock_mode():
        _log.warning("no Groq API key set — Whisperer LLM running in MOCK MODE")
        return mock_fallback() if mock_fallback is not None else {}

    try:
        from agents.groq_utils import call_llm_json as groq_json
    except ImportError as exc:  # pragma: no cover
        _log.error("agents.groq_utils unavailable (%s)", exc)
        return mock_fallback() if mock_fallback is not None else {}

    prompt = f"{system.strip()}\n\n{user.strip()}" if system else user

    try:
        result = await groq_json(prompt)
    except Exception as exc:  # noqa: BLE001 - comms must never crash the pipeline
        _log.error("Groq call failed: %s", exc)
        return mock_fallback() if mock_fallback is not None else {}

    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0]

    _log.error("Groq returned no usable JSON object")
    return mock_fallback() if mock_fallback is not None else {}
