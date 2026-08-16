"""Text-to-speech for the drive-time audio briefing.

Renders the Executive Whisperer script as an MP3 the admin can play on the
way to a meeting. ElevenLabs over plain REST — no SDK, matching how
whatsapp_notifier.py talks to Green API.

Entirely optional. With no ELEVENLABS_API_KEY the whisper is still generated
and still delivered as text; `synthesize()` just returns None and the caller
carries on. Nothing in the meeting flow depends on audio succeeding.

Files land in settings.AUDIO_DIR and main.py serves that directory read-only
at /audio, so the frontend can play the clip straight from a <audio> tag.
"""

import re
from pathlib import Path

import httpx

from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = 60.0


def is_available() -> bool:
    """True when a synthesis attempt could actually reach a provider."""
    return bool(settings.ELEVENLABS_API_KEY)


def _safe_stem(name: str) -> str:
    """A filename component that cannot escape AUDIO_DIR."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower()
    return cleaned[:60] or "briefing"


def _unpunctuated(text: str) -> str:
    """Drop trailing sentence punctuation before embedding text mid-sentence,
    so a quoted objection does not come out as "QuickBooks.."."""
    return str(text).strip().rstrip(".!?,;:")


def script_from_whisper(whisper: dict, company_name: str) -> str:
    """Flatten a whisper briefing into something worth hearing out loud.

    Written as speech, not as a document: no bullet markers, no headings the
    listener would have to picture. Truncated to TTS_MAX_CHARS so the clip
    stays around the minute it is meant to be.
    """
    parts: list[str] = [f"Meeting with {company_name} in thirty minutes."]

    if whisper.get("customer_problem"):
        parts.append(f"Their problem. {whisper['customer_problem']}")

    if whisper.get("recommended_service"):
        parts.append(f"You are pitching {whisper['recommended_service']}.")

    if whisper.get("opening_line"):
        parts.append(f"Open with this. {whisper['opening_line']}")

    objections = [
        obj
        for obj in (whisper.get("objections") or [])
        if isinstance(obj, dict) and obj.get("objection")
    ]
    if objections:
        parts.append("Expect these objections.")
        for obj in objections[:2]:
            rebuttal = (
                obj.get("rebuttal")
                or "acknowledge it and bring it back to their problem"
            )
            parts.append(
                f"They will say, {_unpunctuated(obj['objection'])}. "
                f"You answer, {_unpunctuated(rebuttal)}."
            )

    key_points = [p for p in (whisper.get("key_points") or []) if p]
    if key_points:
        parts.append(
            "Points to land. "
            + ". ".join(_unpunctuated(str(p)) for p in key_points[:3])
            + "."
        )

    parts.append("Good luck.")

    script = " ".join(parts)
    if len(script) > settings.TTS_MAX_CHARS:
        script = script[: settings.TTS_MAX_CHARS].rsplit(".", 1)[0] + "."
    return script


async def synthesize(text: str, filename_stem: str) -> Path | None:
    """Render `text` to an MP3 under AUDIO_DIR and return its path.

    Returns None — never raises — when no key is set, the request fails, or
    the response is empty. Callers treat audio as a bonus on top of the text
    briefing, so a None here is a normal outcome, not an error path.
    """
    if not is_available():
        log.info("tts: no ELEVENLABS_API_KEY set — skipping the audio briefing")
        return None

    if not text.strip():
        log.warning("tts: refusing to synthesize an empty script")
        return None

    url = (
        f"{settings.ELEVENLABS_API_URL.rstrip('/')}"
        f"/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"
    )
    payload = {
        "text": text,
        "model_id": settings.ELEVENLABS_MODEL_ID,
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                url,
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json=payload,
            )
            response.raise_for_status()
            audio = response.content
    except Exception as exc:  # noqa: BLE001 — audio is never worth failing over
        log.error("tts: ElevenLabs synthesis failed: %s", exc)
        return None

    if not audio:
        log.error("tts: ElevenLabs returned an empty body")
        return None

    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.AUDIO_DIR / f"{_safe_stem(filename_stem)}.mp3"
    try:
        path.write_bytes(audio)
    except OSError as exc:
        log.error("tts: could not write %s: %s", path, exc)
        return None

    log.info("tts: wrote %s (%d bytes)", path.name, len(audio))
    return path
