"""
TEMPORARY — delete this file once Wajeeh's real backend/config/settings.py,
backend/utils/logger.py, and backend/db/crud.py land on main.

This module fakes exactly the three things the comms layer depends on that
Wajeeh owns: settings, logging, and the DB (crud). It exists so the comms
layer (Sufiyan's responsibility per FOLDER_STRUCTURE.md) can be built and
tested independently while backend/ is otherwise empty.

See conflicts.md at the repo root for the full list of what needs to be
reconciled when the real modules land — CRUD function signatures in
particular are written to match that document exactly, so swapping this
shim out for the real db/crud.py should require zero changes to any
comms/*.py module.

Column names below mirror .claude/skills/database-schema.md.
"""

import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# settings — mirrors the attribute-access interface of a pydantic
# BaseSettings object (backend/config/settings.py, per FOLDER_STRUCTURE.md).
# ---------------------------------------------------------------------------
class _ShimSettings:
    def __init__(self) -> None:
        self.ANTHROPIC_API_KEY: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
        self.RESEND_API_KEY: Optional[str] = os.environ.get("RESEND_API_KEY")
        self.SENDER_EMAIL: Optional[str] = os.environ.get("SENDER_EMAIL")
        self.TWILIO_ACCOUNT_SID: Optional[str] = os.environ.get("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN: Optional[str] = os.environ.get("TWILIO_AUTH_TOKEN")
        self.TWILIO_WHATSAPP_FROM: Optional[str] = os.environ.get("TWILIO_WHATSAPP_FROM")
        self.ADMIN_WHATSAPP_NUMBER: Optional[str] = os.environ.get("ADMIN_WHATSAPP_NUMBER")
        self.CALCOM_API_KEY: Optional[str] = os.environ.get("CALCOM_API_KEY")


settings = _ShimSettings()


# ---------------------------------------------------------------------------
# logger — stdlib logging, never print() (CLAUDE.md rule).
# ---------------------------------------------------------------------------
_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
        )
        _configured = True
    return logging.getLogger(name)


_log = get_logger("comms.shim")


# ---------------------------------------------------------------------------
# crud — in-memory dict-backed store. Seeded with 3 leads/contacts matching
# data/seeds/replies_seed.json so classify() + decide_next_action() have
# something real to operate on end-to-end.
#
# Function signatures match "What You Depend On" in sufiyan_work.md:
#   create_email, get_all_emails, create_meeting, get_all_meetings,
#   create_reply, get_emails_needing_followup
# plus the implied helpers the comms modules need: get_lead,
# get_primary_contact, update_lead_stage, create_followup.
# ---------------------------------------------------------------------------
class _ShimCRUD:
    def __init__(self) -> None:
        self._leads = {
            "lead_001": {
                "id": "lead_001",
                "company_name": "AlphaLogistics",
                "pipeline_stage": "Contacted",
                "recommended_service": "WhatsApp AI Chatbot with CRM Integration",
                "research_summary": "High volume of WhatsApp customer inquiries "
                "overwhelming a 5-person support team.",
            },
            "lead_002": {
                "id": "lead_002",
                "company_name": "BetaFreight",
                "pipeline_stage": "Contacted",
                "recommended_service": "AI Customer Support Automation",
                "research_summary": "Slow response times on freight status inquiries.",
            },
            "lead_003": {
                "id": "lead_003",
                "company_name": "GammaSupply",
                "pipeline_stage": "Contacted",
                "recommended_service": "AI Customer Support Automation",
                "research_summary": "Manual ticket triage causing delays.",
            },
        }
        self._contacts = {
            "lead_001": {
                "id": "contact_001",
                "lead_id": "lead_001",
                "name": "Omar Al-Rashid",
                "role": "CEO",
                "email": "ceo@alphalogistics.ae",
                "is_primary": True,
            },
            "lead_002": {
                "id": "contact_002",
                "lead_id": "lead_002",
                "name": "Ops Lead",
                "role": "Operations Manager",
                "email": "ops@betafreight.com",
                "is_primary": True,
            },
            "lead_003": {
                "id": "contact_003",
                "lead_id": "lead_003",
                "name": "Tech Lead",
                "role": "IT Manager",
                "email": "tech@gammasupply.com",
                "is_primary": True,
            },
        }
        self._emails: list[dict] = []
        self._replies: list[dict] = []
        self._meetings: list[dict] = []
        self._followups: list[dict] = []

    # -- emails ------------------------------------------------------------
    def create_email(
        self,
        lead_id: str,
        contact_id: str,
        subject: str,
        body: str,
        status: str,
        sent_at: Optional[datetime] = None,
    ) -> dict:
        record = {
            "id": f"email_{uuid.uuid4().hex[:8]}",
            "lead_id": lead_id,
            "contact_id": contact_id,
            "subject": subject,
            "body": body,
            "status": status,
            "sent_at": sent_at or datetime.now(timezone.utc),
        }
        self._emails.append(record)
        _log.info("crud(shim): create_email lead_id=%s status=%s", lead_id, status)
        return record

    def get_all_emails(self) -> list[dict]:
        return list(self._emails)

    def get_emails_needing_followup(self, days: int = 3) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        replied_email_ids = {r["email_id"] for r in self._replies}
        followed_up_email_ids = {f["email_id"] for f in self._followups}
        return [
            e
            for e in self._emails
            if e["status"] == "sent"
            and e["sent_at"] <= cutoff
            and e["id"] not in replied_email_ids
            and e["id"] not in followed_up_email_ids
        ]

    # -- replies -------------------------------------------------------------
    def create_reply(self, email_id: str, raw_body: str, received_at: Optional[datetime] = None) -> dict:
        record = {
            "id": f"reply_{uuid.uuid4().hex[:8]}",
            "email_id": email_id,
            "raw_body": raw_body,
            "received_at": received_at or datetime.now(timezone.utc),
        }
        self._replies.append(record)
        _log.info("crud(shim): create_reply email_id=%s", email_id)
        return record

    # -- meetings --------------------------------------------------------
    def create_meeting(
        self,
        lead_id: str,
        contact_id: str,
        meeting_link: str,
        status: str = "link_sent",
        scheduled_at: Optional[datetime] = None,
        briefing: Optional[dict] = None,
    ) -> dict:
        record = {
            "id": f"meeting_{uuid.uuid4().hex[:8]}",
            "lead_id": lead_id,
            "contact_id": contact_id,
            "meeting_link": meeting_link,
            "status": status,
            "scheduled_at": scheduled_at,
            "briefing": briefing,
            "admin_notified": False,
        }
        self._meetings.append(record)
        _log.info("crud(shim): create_meeting lead_id=%s link=%s", lead_id, meeting_link)
        return record

    def get_all_meetings(self) -> list[dict]:
        return list(self._meetings)

    # -- follow-ups --------------------------------------------------------
    def create_followup(self, lead_id: str, email_id: str, scheduled_for: datetime, status: str = "sent") -> dict:
        record = {
            "id": f"followup_{uuid.uuid4().hex[:8]}",
            "lead_id": lead_id,
            "email_id": email_id,
            "scheduled_for": scheduled_for,
            "status": status,
        }
        self._followups.append(record)
        _log.info("crud(shim): create_followup lead_id=%s", lead_id)
        return record

    # -- leads / contacts (read helpers) ------------------------------------
    def get_lead(self, lead_id: str) -> Optional[dict]:
        return self._leads.get(lead_id)

    def get_primary_contact(self, lead_id: str) -> Optional[dict]:
        return self._contacts.get(lead_id)

    def update_lead_stage(self, lead_id: str, stage: str) -> Optional[dict]:
        lead = self._leads.get(lead_id)
        if lead is not None:
            lead["pipeline_stage"] = stage
            _log.info("crud(shim): update_lead_stage lead_id=%s stage=%s", lead_id, stage)
        return lead


crud = _ShimCRUD()
