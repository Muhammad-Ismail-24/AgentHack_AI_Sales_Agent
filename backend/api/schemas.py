"""Pydantic request/response models. Routes return these, never raw dicts.

Field names match db/models.py exactly, which in turn matches
frontend/src/lib/types.ts. Change one, change all three.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Base for anything read straight off a SQLAlchemy row."""

    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════════════════════════════
# Company / onboarding
# ══════════════════════════════════════════════════════════════════════

class CompanyTextRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Pasted company description")
    company_name: str | None = None


class CompanyUploadResponse(BaseModel):
    session_id: str
    company_name: str
    status: str = "ingested"
    chars_ingested: int | None = None
    message: str | None = None


# ══════════════════════════════════════════════════════════════════════
# ICP
# ══════════════════════════════════════════════════════════════════════

class ICPRequest(BaseModel):
    session_id: str
    location: str
    industry: str
    company_size: str
    special_focus: str | None = None


class ICPResponse(BaseModel):
    session_id: str
    icp: dict[str, Any]


# ══════════════════════════════════════════════════════════════════════
# Pipeline
# ══════════════════════════════════════════════════════════════════════

class PipelineStartRequest(BaseModel):
    session_id: str


class PipelineStartResponse(BaseModel):
    session_id: str
    status: str = "running"


class PipelineStatusResponse(BaseModel):
    session_id: str
    stage: str
    is_running: bool = False
    raw_leads_count: int = 0
    filtered_count: int = 0
    qualified_count: int = 0
    outreach_count: int = 0
    total_leads: int = 0
    stage_counts: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


# ══════════════════════════════════════════════════════════════════════
# Core entities
# ══════════════════════════════════════════════════════════════════════

class ContactResponse(ORMModel):
    id: str
    lead_id: str
    name: str | None = None
    role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    is_primary: bool = False


class EmailResponse(ORMModel):
    id: str
    lead_id: str
    contact_id: str | None = None
    subject: str | None = None
    body: str | None = None
    status: str
    sent_at: datetime | None = None
    created_at: datetime


class ReplyResponse(ORMModel):
    id: str
    email_id: str
    raw_body: str | None = None
    classification: str | None = None
    summary: str | None = None
    next_action: str | None = None
    received_at: datetime


class MeetingResponse(ORMModel):
    id: str
    lead_id: str
    contact_id: str | None = None
    meeting_link: str | None = None
    scheduled_at: datetime | None = None
    briefing: dict[str, Any] | None = None
    admin_notified: bool = False
    status: str
    created_at: datetime


class FollowUpResponse(ORMModel):
    id: str
    lead_id: str
    original_email_id: str
    followup_email_id: str | None = None
    scheduled_for: datetime | None = None
    status: str
    created_at: datetime


class PipelineEventResponse(ORMModel):
    id: str
    lead_id: str
    from_stage: str | None = None
    to_stage: str | None = None
    reason: str | None = None
    created_at: datetime


class LeadResponse(ORMModel):
    id: str
    company_name: str
    website: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None
    pipeline_stage: str
    lead_score: int | None = None
    score_explanation: str | None = None
    recommended_service: str | None = None
    pitch_angle: str | None = None
    icp_fit: bool | None = None
    research_summary: str | None = None
    apollo_data: dict[str, Any] | None = None
    session_id: str | None = None
    created_at: datetime
    updated_at: datetime
    contacts: list[ContactResponse] = Field(default_factory=list)


class LeadDetailResponse(BaseModel):
    """Everything on the lead detail page, in one request."""

    lead: LeadResponse
    contacts: list[ContactResponse] = Field(default_factory=list)
    emails: list[EmailResponse] = Field(default_factory=list)
    replies: list[ReplyResponse] = Field(default_factory=list)
    meetings: list[MeetingResponse] = Field(default_factory=list)
    events: list[PipelineEventResponse] = Field(default_factory=list)


class LeadUpdateRequest(BaseModel):
    """PATCH /leads/{id} — every field optional, only what's sent is applied."""

    pipeline_stage: str | None = None
    lead_score: int | None = Field(default=None, ge=0, le=100)
    recommended_service: str | None = None
    pitch_angle: str | None = None
    research_summary: str | None = None
    icp_fit: bool | None = None


# ══════════════════════════════════════════════════════════════════════
# Shared / misc
# ══════════════════════════════════════════════════════════════════════

class InboxItem(BaseModel):
    """A reply joined with the lead and contact it came from — Inbox page."""

    reply: ReplyResponse
    email: EmailResponse
    lead_id: str
    company_name: str
    contact_name: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "unknown"
    version: str = "0.1.0"


class MessageResponse(BaseModel):
    success: bool = True
    message: str | None = None
