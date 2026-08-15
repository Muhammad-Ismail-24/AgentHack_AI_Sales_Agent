"""GET /leads, GET /leads/{id}, PATCH /leads/{id} — everything the
Pipeline, Leads, and Lead Detail pages read.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    LeadDetailResponse,
    LeadResponse,
    LeadUpdateRequest,
    MessageResponse,
)
from db import crud
from db.database import get_db
from db.models import PIPELINE_STAGES
from memory.long_term import long_term_memory
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    session_id: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[LeadResponse]:
    """All leads with their contacts. Optionally scoped to a session or stage."""
    leads = await crud.get_all_leads(db, session_id)
    if stage:
        leads = [lead for lead in leads if lead.pipeline_stage == stage]
    return [LeadResponse.model_validate(lead) for lead in leads]


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead_detail(
    lead_id: str, db: AsyncSession = Depends(get_db)
) -> LeadDetailResponse:
    """Full history for one lead: contacts, emails, replies, meetings, timeline."""
    history = await long_term_memory.recall_lead_history(db, lead_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    return LeadDetailResponse(
        lead=history["lead"],
        contacts=history["contacts"],
        emails=history["emails"],
        replies=history["replies"],
        meetings=history["meetings"],
        events=history["events"],
    )


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str, payload: LeadUpdateRequest, db: AsyncSession = Depends(get_db)
) -> LeadResponse:
    """Manually edit a lead — mainly used to drag it to a different stage."""
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    new_stage = updates.pop("pipeline_stage", None)
    if new_stage is not None and new_stage not in PIPELINE_STAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown stage '{new_stage}'. Valid stages: {', '.join(PIPELINE_STAGES)}",
        )

    lead = await crud.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    if updates:
        lead = await crud.update_lead(db, lead_id, updates)
    if new_stage is not None:
        lead = await crud.update_lead_stage(db, lead_id, new_stage, "Moved manually")

    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(
    lead_id: str, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """Remove a lead and everything hanging off it. Used to tidy up before a demo."""
    lead = await crud.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")
    await db.delete(lead)
    await db.commit()
    log.info("deleted lead %s", lead_id)
    return MessageResponse(success=True, message=f"Deleted lead {lead_id}.")
