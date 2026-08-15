"""Long-term memory — a readable interface over the database.

Nothing here talks SQL; it all goes through db/crud.py. The point is that an
agent can say "remember this lead" or "what do we know about lead X" without
knowing anything about the schema.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.models import Contact, Lead
from utils.logger import get_logger

log = get_logger(__name__)


class LongTermMemory:
    """Durable memory: leads, contacts, emails, replies, meetings, timeline."""

    async def remember_lead(
        self, db: AsyncSession, lead_dict: dict[str, Any], session_id: str
    ) -> Lead | None:
        """Store (or update) one lead. Returns the persisted row."""
        saved = await crud.upsert_leads_from_pipeline(db, [lead_dict], session_id)
        return saved[0] if saved else None

    async def remember_leads(
        self, db: AsyncSession, leads: list[dict[str, Any]], session_id: str
    ) -> list[Lead]:
        """Bulk version — what the orchestrator calls at the end of a run."""
        return await crud.upsert_leads_from_pipeline(db, leads, session_id)

    async def remember_contact(
        self, db: AsyncSession, contact_dict: dict[str, Any], lead_id: str
    ) -> Contact:
        return await crud.create_contact(db, contact_dict, lead_id)

    async def recall_lead_history(
        self, db: AsyncSession, lead_id: str
    ) -> dict[str, Any] | None:
        """Everything known about a lead, assembled in one dict.

        Returns None when the lead does not exist, so callers can 404 cleanly.
        """
        lead = await crud.get_lead(db, lead_id)
        if lead is None:
            return None

        return {
            "lead": lead,
            "contacts": await crud.get_contacts_for_lead(db, lead_id),
            "emails": await crud.get_emails_for_lead(db, lead_id),
            "replies": await crud.get_replies_for_lead(db, lead_id),
            "meetings": await crud.get_meetings_for_lead(db, lead_id),
            "events": await crud.get_events_for_lead(db, lead_id),
        }

    async def what_stage_is(self, db: AsyncSession, lead_id: str) -> str | None:
        lead = await crud.get_lead(db, lead_id)
        return lead.pipeline_stage if lead else None

    async def what_do_we_know_about(
        self, db: AsyncSession, company_name: str, session_id: str | None = None
    ) -> dict[str, Any] | None:
        """Same as recall_lead_history, looked up by company name."""
        lead = await crud.get_lead_by_company(db, company_name, session_id)
        if lead is None:
            return None
        return await self.recall_lead_history(db, lead.id)

    async def move_lead_to(
        self, db: AsyncSession, lead_id: str, stage: str, reason: str | None = None
    ) -> Lead | None:
        return await crud.update_lead_stage(db, lead_id, stage, reason)


long_term_memory = LongTermMemory()
