"""Read-only endpoints the dashboard needs.

GET /inbox is mine — it joins replies to their email, lead, and contact so the
Inbox page can render in one request.

GET /emails and GET /meetings are Sufiyan's (backend/api/routes/emails.py and
meetings.py, which also own the POST side). This router is registered *after*
his in main.py, so once his branch merges his handlers match first and these
become dead weight that can be deleted. Until then they keep the Inbox and
Meetings pages working against seeded data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import EmailResponse, InboxItem, MeetingResponse
from db import crud
from db.database import get_db
from db.models import Contact
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/inbox", response_model=list[InboxItem])
async def get_inbox(db: AsyncSession = Depends(get_db)) -> list[InboxItem]:
    """Every reply received, newest first, with its lead and contact resolved."""
    replies = await crud.get_all_replies(db)

    items: list[InboxItem] = []
    for reply in replies:
        email = await crud.get_email(db, reply.email_id)
        if email is None:
            continue

        lead = await crud.get_lead(db, email.lead_id)
        contact = await db.get(Contact, email.contact_id) if email.contact_id else None

        items.append(
            InboxItem(
                reply=reply,
                email=email,
                lead_id=email.lead_id,
                company_name=lead.company_name if lead else "Unknown company",
                contact_name=contact.name if contact else None,
            )
        )

    return items


@router.get("/emails", response_model=list[EmailResponse])
async def list_emails(db: AsyncSession = Depends(get_db)) -> list[EmailResponse]:
    """All emails, newest first. Superseded by Sufiyan's emails router."""
    emails = await crud.get_all_emails(db)
    return [EmailResponse.model_validate(e) for e in emails]


@router.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(db: AsyncSession = Depends(get_db)) -> list[MeetingResponse]:
    """All meetings, soonest first. Superseded by Sufiyan's meetings router."""
    meetings = await crud.get_all_meetings(db)
    return [MeetingResponse.model_validate(m) for m in meetings]
