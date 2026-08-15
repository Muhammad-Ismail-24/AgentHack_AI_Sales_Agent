"""GET /inbox — replies joined to their email, lead, and contact.

Sufiyan's routers own `/emails` and `/meetings` (including the POST side) and
are registered ahead of this one in main.py, so only `/inbox` is served here
now. It stays mine because the Inbox page needs the join done server-side —
Firestore cannot do it in a query.
"""

from fastapi import APIRouter

from api.schemas import InboxItem
from db import acrud
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/inbox", response_model=list[InboxItem])
async def get_inbox() -> list[InboxItem]:
    """Every reply received, newest first, with lead and contact resolved."""
    replies = await acrud.get_all_replies()

    # Load leads and contacts once rather than per reply — Firestore charges
    # per document read, and the inbox is polled every 30 seconds.
    leads = {lead["id"]: lead for lead in await acrud.get_all_leads()}

    items: list[InboxItem] = []
    for reply in replies:
        email = await acrud.get_email(reply.get("email_id"))
        if email is None:
            continue

        lead = leads.get(email.get("lead_id"))
        contact = (
            await acrud.get_contact(email["contact_id"])
            if email.get("contact_id")
            else None
        )

        items.append(
            InboxItem(
                reply=reply,
                email=email,
                lead_id=email.get("lead_id"),
                company_name=lead.get("company_name") if lead else "Unknown company",
                contact_name=contact.get("name") if contact else None,
            )
        )

    return items
