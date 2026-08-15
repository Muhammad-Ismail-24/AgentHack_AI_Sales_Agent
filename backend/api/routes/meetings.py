"""
GET /meetings, POST /meetings/create — Sufiyan's full ownership per
sufiyan_work.md.

Same isolation approach as emails.py in this directory: router-local
schemas, no shared backend/api/schemas.py dependency, no changes to
routes/__init__.py. See that file's docstring and conflicts.md for the
full rationale.

Registration (not done here — backend/main.py doesn't exist yet):
    app.include_router(meetings_router, prefix="/meetings")
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from comms._deps import crud, get_logger
from comms.meeting_manager import MeetingManager

router = APIRouter()
_log = get_logger("api.meetings")


# --- schemas (local to this router — see isolation note above) -------------
class MeetingSchema(BaseModel):
    id: str
    lead_id: str
    contact_id: str
    meeting_link: str
    status: str
    scheduled_at: Optional[datetime] = None
    briefing: Optional[Dict[str, Any]] = None
    admin_notified: bool = False


class CreateMeetingRequest(BaseModel):
    lead_id: str


class CreateMeetingResponse(BaseModel):
    meeting_link: Optional[str] = None
    email_sent: bool = False
    whatsapp_sent: bool = False


# --- routes ------------------------------------------------------------
@router.get("", response_model=List[MeetingSchema])
async def list_meetings() -> List[MeetingSchema]:
    return [MeetingSchema(**m) for m in crud.get_all_meetings()]


@router.post("/create", response_model=CreateMeetingResponse)
async def create_meeting(payload: CreateMeetingRequest) -> CreateMeetingResponse:
    result = await MeetingManager().handle_meeting_request(payload.lead_id)
    if result.get("meeting_link") is None:
        _log.warning("create_meeting: no meeting link generated for lead_id=%s", payload.lead_id)
    return CreateMeetingResponse(**result)
