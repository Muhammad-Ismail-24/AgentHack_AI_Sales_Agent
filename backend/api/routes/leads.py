"""GET /leads, GET /leads/{id}, PATCH /leads/{id} — everything the
Pipeline, Leads, and Lead Detail pages read.
"""

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    LeadDetailResponse,
    LeadResponse,
    LeadUpdateRequest,
    MessageResponse,
)
from db import acrud
from db.models import PIPELINE_STAGES
from memory.long_term import long_term_memory
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


async def _with_contacts(lead: dict) -> dict:
    """Firestore has no joins — attach contacts the frontend expects inline."""
    return {**lead, "contacts": await acrud.get_contacts_for_lead(lead["id"])}


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    session_id: str | None = Query(default=None),
    stage: str | None = Query(default=None),
) -> list[LeadResponse]:
    """All leads with their contacts. Optionally scoped to a session or stage."""
    leads = await acrud.get_all_leads(session_id)
    if stage:
        leads = [lead for lead in leads if lead.get("pipeline_stage") == stage]

    return [
        LeadResponse.model_validate(await _with_contacts(lead)) for lead in leads
    ]


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead_detail(lead_id: str) -> LeadDetailResponse:
    """Full history for one lead: contacts, emails, replies, meetings, timeline."""
    history = await long_term_memory.recall_lead_history(lead_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    lead = {**history["lead"], "contacts": history["contacts"]}

    return LeadDetailResponse(
        lead=LeadResponse.model_validate(lead),
        contacts=history["contacts"],
        emails=history["emails"],
        replies=history["replies"],
        meetings=history["meetings"],
        events=history["events"],
    )


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: str, payload: LeadUpdateRequest) -> LeadResponse:
    """Manually edit a lead — mainly used to move it to a different stage."""
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    new_stage = updates.pop("pipeline_stage", None)
    if new_stage is not None and new_stage not in PIPELINE_STAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown stage '{new_stage}'. Valid stages: {', '.join(PIPELINE_STAGES)}",
        )

    lead = await acrud.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    if updates:
        lead = await acrud.update_lead(lead_id, updates) or lead
    if new_stage is not None:
        lead = await acrud.update_lead_stage(lead_id, new_stage, "Moved manually") or lead

    return LeadResponse.model_validate(await _with_contacts(lead))


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(lead_id: str) -> MessageResponse:
    """Remove a lead and everything hanging off it."""
    if not await acrud.delete_lead(lead_id):
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")
    return MessageResponse(success=True, message=f"Deleted lead {lead_id}.")
