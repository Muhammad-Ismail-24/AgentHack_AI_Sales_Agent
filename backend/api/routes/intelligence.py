"""The extra-credit intelligence layer, all on demand.

  POST /intelligence/leads/{id}/devils-advocate  — hold the debate
  GET  /intelligence/leads/{id}/devils-advocate  — the last verdict
  POST /intelligence/leads/{id}/autopsy          — post-mortem a dead lead
  GET  /intelligence/leads/{id}/autopsy          — the last post-mortem
  GET  /intelligence/autopsies/insights          — what they all argue for
  POST /intelligence/meetings/{id}/whisper       — write the pre-call script
  GET  /intelligence/meetings/{id}/whisper       — the stored script
  POST /intelligence/meetings/{id}/whisper/audio — render it as a voice note

Nothing here runs during a pipeline pass, so a normal run costs exactly what
it did before this file existed. Every POST is human-triggered from the UI —
the debate and the post-mortem each spend LLM calls, and the audio one spends
TTS credit, so none of them fires on its own.
"""

from fastapi import APIRouter, HTTPException

from api import orchestrator_bridge
from api.schemas import (
    AutopsyInsightsResponse,
    AutopsyResponse,
    VerdictResponse,
    WhisperAudioResponse,
    WhisperResponse,
)
from db import acrud
from db.models import REJECTED_STAGES
from memory.long_term import long_term_memory
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _unavailable(exc: Exception) -> HTTPException:
    """The orchestrator being missing is a dependency failure, not a bug in
    the request — 503 so the frontend shows "try again" rather than "bad
    input"."""
    return HTTPException(status_code=503, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════
# Devil's Advocate
# ══════════════════════════════════════════════════════════════════════

@router.post("/leads/{lead_id}/devils-advocate", response_model=VerdictResponse)
async def run_devils_advocate(lead_id: str) -> VerdictResponse:
    """Two agents argue over this lead; a third resolves it into a score."""
    lead = await acrud.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    lead_with_contacts = {**lead, "contacts": await acrud.get_contacts_for_lead(lead_id)}

    try:
        debate = await orchestrator_bridge.run_devils_advocate(lead=lead_with_contacts)
    except RuntimeError as exc:
        raise _unavailable(exc) from exc

    verdict = await acrud.create_verdict(lead_id, debate)
    return VerdictResponse.model_validate(verdict)


@router.get("/leads/{lead_id}/devils-advocate", response_model=VerdictResponse)
async def get_devils_advocate(lead_id: str) -> VerdictResponse:
    """The most recent verdict for this lead."""
    verdict = await acrud.get_latest_verdict(lead_id)
    if verdict is None:
        raise HTTPException(
            status_code=404,
            detail=f"No debate has been held for lead {lead_id} yet.",
        )
    return VerdictResponse.model_validate(verdict)


# ══════════════════════════════════════════════════════════════════════
# Deal Autopsy
# ══════════════════════════════════════════════════════════════════════

@router.post("/leads/{lead_id}/autopsy", response_model=AutopsyResponse)
async def run_autopsy(lead_id: str) -> AutopsyResponse:
    """Post-mortem a dead lead: cause of death, misfire, correction.

    Refuses on a lead that is still live — a "cause of death" for a deal
    still in play is a fabrication, and every finding here is supposed to be
    grounded in how the deal actually ended.
    """
    history = await long_term_memory.recall_lead_history(lead_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    stage = history["lead"].get("pipeline_stage")
    if stage not in REJECTED_STAGES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Lead {lead_id} is still active (stage '{stage}'). An autopsy "
                f"only runs on a lead in one of: {', '.join(REJECTED_STAGES)}."
            ),
        )

    try:
        findings = await orchestrator_bridge.run_autopsy(
            lead=history["lead"],
            contacts=history["contacts"],
            emails=history["emails"],
            replies=history["replies"],
            events=history["events"],
        )
    except RuntimeError as exc:
        raise _unavailable(exc) from exc

    autopsy = await acrud.create_autopsy(lead_id, findings)
    return AutopsyResponse.model_validate(autopsy)


@router.get("/leads/{lead_id}/autopsy", response_model=AutopsyResponse)
async def get_autopsy(lead_id: str) -> AutopsyResponse:
    autopsy = await acrud.get_latest_autopsy(lead_id)
    if autopsy is None:
        raise HTTPException(
            status_code=404,
            detail=f"No autopsy has been run on lead {lead_id} yet.",
        )
    return AutopsyResponse.model_validate(autopsy)


@router.get("/autopsies/insights", response_model=AutopsyInsightsResponse)
async def get_autopsy_insights() -> AutopsyInsightsResponse:
    """The closed loop: what every post-mortem so far says to change.

    A rollup over documents already in Firestore — no LLM call, so the panel
    is free to refresh.
    """
    autopsies = await acrud.get_all_autopsies()
    try:
        summary = orchestrator_bridge.summarise_autopsies(autopsies=autopsies)
    except RuntimeError as exc:
        raise _unavailable(exc) from exc
    return AutopsyInsightsResponse.model_validate(summary)


# ══════════════════════════════════════════════════════════════════════
# Executive Whisperer
# ══════════════════════════════════════════════════════════════════════

async def _whisper_response(
    meeting: dict, whisper: dict, audio_url: str | None = None
) -> WhisperResponse:
    lead = await acrud.get_lead(meeting["lead_id"])
    return WhisperResponse(
        meeting_id=meeting["id"],
        lead_id=meeting["lead_id"],
        company_name=(lead or {}).get("company_name") or "Unknown company",
        customer_problem=whisper.get("customer_problem"),
        recommended_service=whisper.get("recommended_service"),
        evidence=whisper.get("evidence"),
        opening_line=whisper.get("opening_line"),
        key_points=[str(p) for p in (whisper.get("key_points") or [])],
        objections=[
            obj
            for obj in (whisper.get("objections") or [])
            if isinstance(obj, dict) and obj.get("objection")
        ],
        watch_out_for=[str(w) for w in (whisper.get("watch_out_for") or [])],
        audio_url=audio_url,
    )


@router.post("/meetings/{meeting_id}/whisper", response_model=WhisperResponse)
async def build_whisper(meeting_id: str) -> WhisperResponse:
    """Write the pre-call script: opening line, objections, rebuttals."""
    meeting = await acrud.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found.")

    try:
        whisper = await orchestrator_bridge.build_meeting_whisper(meeting_id=meeting_id)
    except RuntimeError as exc:
        raise _unavailable(exc) from exc

    if whisper is None:
        raise HTTPException(
            status_code=409,
            detail=f"Meeting {meeting_id} has no lead attached, so no script can be written.",
        )
    return await _whisper_response(meeting, whisper)


@router.get("/meetings/{meeting_id}/whisper", response_model=WhisperResponse)
async def get_whisper(meeting_id: str) -> WhisperResponse:
    """The script already stored on the meeting, if one has been written."""
    meeting = await acrud.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found.")

    whisper = meeting.get("briefing")
    if not whisper:
        raise HTTPException(
            status_code=404,
            detail=f"No script has been written for meeting {meeting_id} yet.",
        )
    return await _whisper_response(meeting, whisper)


@router.post("/meetings/{meeting_id}/whisper/audio", response_model=WhisperAudioResponse)
async def build_whisper_audio(meeting_id: str) -> WhisperAudioResponse:
    """Render the script as a 60-second voice note and WhatsApp it to the admin.

    Returns 200 with a null `audio_url` when no TTS key is configured — audio
    is a layer on top of the text script, and the script is what the meeting
    actually depends on.
    """
    meeting = await acrud.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found.")

    try:
        result = await orchestrator_bridge.deliver_whisper_audio(meeting_id=meeting_id)
    except RuntimeError as exc:
        raise _unavailable(exc) from exc

    audio_url = result.get("audio_url")
    return WhisperAudioResponse(
        meeting_id=meeting_id,
        audio_url=audio_url,
        script=result.get("script"),
        whatsapp_sent=bool(result.get("whatsapp_sent")),
        message=(
            "Audio briefing ready."
            if audio_url
            else "No audio was generated — set ELEVENLABS_API_KEY to enable the "
                 "drive-time briefing. The text script is unaffected."
        ),
    )
