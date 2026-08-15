"""Shared helpers for calling the LLM and parsing its JSON responses.

Not one of the 9 pipeline nodes — a small internal utility used by all of
them so each agent doesn't reimplement "call the LLM, then robustly parse
the JSON out of the response". Prompts still live only in config/prompts.py;
this file just wires up the model client and response parsing.

LLM provider: Google Gemini, via langchain-google-genai.
"""

import json
import re

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from utils.logger import logger

_llm: ChatGoogleGenerativeAI | None = None
_model_name: str | None = None


def _build(model: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.google_api_key,
        max_output_tokens=settings.GEMINI_MAX_TOKENS,
        temperature=0.2,
        timeout=60,
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


async def call_llm_json(prompt: str) -> dict | list | None:
    """Send `prompt` to the LLM and return the parsed JSON response, or None."""
    messages = [HumanMessage(content=prompt)]

    try:
        response = await get_llm().ainvoke(messages)
    except Exception as exc:  # noqa: BLE001
        # A retired model reports itself as a 404 / NotFound.
        if "404" not in str(exc) and "not found" not in str(exc).lower():
            raise
        fallback = _switch_to_fallback()
        if fallback is None:
            raise
        response = await fallback.ainvoke(messages)

    content = (
        response.content
        if isinstance(response.content, str)
        else str(response.content)
    )
    return extract_json(content)
