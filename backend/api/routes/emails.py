"""
GET /emails, POST /emails/send — Sufiyan's full ownership per
sufiyan_work.md.

Isolation note: this router defines its own request/response schemas
locally rather than importing from a shared backend/api/schemas.py — that
file doesn't exist yet (it's Person 3/Wajeeh's, per FOLDER_STRUCTURE.md's
file guide) and won't for a while. Keeping this router fully self-contained
means Wajeeh's own routes and schemas can land in this same directory
without either of us touching a file the other owns. Once
backend/api/schemas.py exists, EmailSchema/SendEmailRequest/
SendEmailResponse below are candidates to move there — see conflicts.md.

Registration (not done here — backend/main.py doesn't exist yet):
    app.include_router(emails_router, prefix="/emails")
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from comms._deps import crud, get_logger
from comms.email_sender import EmailSender

router = APIRouter()
_log = get_logger("api.emails")


# --- schemas (local to this router — see isolation note above) -------------
class EmailSchema(BaseModel):
    id: str
    lead_id: str
    # Optional, matching email_doc: a lead whose domain Hunter could not
    # enrich has no contact, and its draft is still worth showing. Requiring
    # a str here made one such row fail validation and took the whole
    # GET /emails response down with a 500.
    contact_id: Optional[str] = None
    subject: str
    body: str
    status: str
    sent_at: Optional[datetime] = None


class SendEmailRequest(BaseModel):
    lead_id: str
    # Also optional so a send attempt on a contactless lead reaches the
    # handler and comes back as "no contact" rather than a 422 the UI has
    # no message for.
    contact_id: Optional[str] = None
    subject: str
    body: str


class SendEmailResponse(BaseModel):
    success: bool
    message: str


# --- routes ------------------------------------------------------------
@router.get("", response_model=List[EmailSchema])
async def list_emails() -> List[EmailSchema]:
    return [EmailSchema(**e) for e in crud.get_all_emails()]


@router.post("/send", response_model=SendEmailResponse)
async def send_email(payload: SendEmailRequest) -> SendEmailResponse:
    if not payload.contact_id:
        # No decision maker was found for this lead, so there is no address
        # to send to. Say so plainly instead of looking up a None id.
        _log.warning("send_email: lead %s has no contact to send to", payload.lead_id)
        return SendEmailResponse(
            success=False,
            message=(
                "This lead has no verified contact yet, so there is no address "
                "to send to. Contacts come from the Hunter lookup during a run."
            ),
        )

    contact = crud.get_contact(payload.contact_id)
    if contact is None:
        _log.warning("send_email: unknown contact_id=%s", payload.contact_id)
        return SendEmailResponse(success=False, message=f"Unknown contact_id: {payload.contact_id}")

    result = await EmailSender().send(
        to_email=contact["email"],
        subject=payload.subject,
        body=payload.body,
        lead_id=payload.lead_id,
        contact_id=payload.contact_id,
    )

    if result.get("success"):
        return SendEmailResponse(success=True, message=f"Email sent (email_id={result.get('email_id')})")
    return SendEmailResponse(success=False, message=result.get("error", "unknown error"))
