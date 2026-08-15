"""Long-term memory — a readable interface over Firestore.

Nothing here talks to Firestore directly; it all goes through db/acrud.py.
The point is that an agent can say "remember this lead" or "what do we know
about lead X" without knowing anything about the collections.
"""

from typing import Any

from db import acrud
from utils.logger import get_logger

log = get_logger(__name__)


class LongTermMemory:
    """Durable memory: leads, contacts, emails, replies, meetings, timeline."""

    async def remember_lead(
        self, lead_dict: dict[str, Any], session_id: str
    ) -> dict | None:
        """Store (or update) one lead. Returns the persisted document."""
        saved = await acrud.upsert_leads_from_pipeline([lead_dict], session_id)
        return saved[0] if saved else None

    async def remember_leads(
        self, leads: list[dict[str, Any]], session_id: str
    ) -> list[dict]:
        """Bulk version — what the orchestrator calls at the end of a run."""
        return await acrud.upsert_leads_from_pipeline(leads, session_id)

    async def remember_contact(
        self, contact_dict: dict[str, Any], lead_id: str
    ) -> dict:
        return await acrud.create_contact(contact_dict, lead_id)

    async def recall_lead_history(self, lead_id: str) -> dict[str, Any] | None:
        """Everything known about a lead, assembled in one dict.

        Returns None when the lead does not exist, so callers can 404 cleanly.
        """
        lead = await acrud.get_lead(lead_id)
        if lead is None:
            return None

        return {
            "lead": lead,
            "contacts": await acrud.get_contacts_for_lead(lead_id),
            "emails": await acrud.get_emails_for_lead(lead_id),
            "replies": await acrud.get_replies_for_lead(lead_id),
            "meetings": await acrud.get_meetings_for_lead(lead_id),
            "events": await acrud.get_events_for_lead(lead_id),
        }

    async def what_stage_is(self, lead_id: str) -> str | None:
        lead = await acrud.get_lead(lead_id)
        return lead.get("pipeline_stage") if lead else None

    async def what_do_we_know_about(
        self, company_name: str, session_id: str | None = None
    ) -> dict[str, Any] | None:
        """Same as recall_lead_history, looked up by company name."""
        lead = await acrud.get_lead_by_company(company_name, session_id)
        if lead is None:
            return None
        return await self.recall_lead_history(lead["id"])

    async def move_lead_to(
        self, lead_id: str, stage: str, reason: str | None = None
    ) -> dict | None:
        return await acrud.update_lead_stage(lead_id, stage, reason)


long_term_memory = LongTermMemory()
