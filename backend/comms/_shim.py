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

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# backend/comms/_shim.py -> backend/comms -> backend -> repo root
_SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seeds"


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
        # Best-effort: make console output UTF-8-safe on platforms (Windows)
        # whose default stdout codepage can't represent characters that show
        # up in log messages and mock payloads — e.g. the emoji and em dash
        # in whatsapp_notifier.py's message templates. Without this, writing
        # them can mangle output or raise inside the logging call.
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except Exception:  # noqa: BLE001 — purely cosmetic, never fatal
                    pass
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
# get_primary_contact, update_lead_stage, create_followup, get_email,
# update_email_status, get_meeting, mark_meeting_admin_notified,
# get_meetings_needing_reminder, get_contact_by_email (added while
# building Steps 4-5 — see conflicts.md for the full up-to-date contract).
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

        self._seed_demo_meeting()

    # -- demo seed loading (Step 8) ------------------------------------------
    def _seed_demo_meeting(self) -> None:
        """
        Pre-load data/seeds/meetings_seed.json into self._meetings so
        GET /meetings has a coherent, ready-to-show demo record without
        requiring a live handle_meeting_request() call first. This makes
        the seed file an actual source of truth for the running system,
        not just a fixture other test scripts happen to read.

        Best-effort: a missing or malformed seed file logs a warning and
        leaves the meeting list empty rather than crashing import — this
        module is imported at process startup, so it must never raise.
        """
        seed_path = _SEEDS_DIR / "meetings_seed.json"
        try:
            seed_meetings = json.loads(seed_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning("Could not load meetings_seed.json (%s) - skipping demo meeting seed", exc)
            return

        for entry in seed_meetings:
            lead_id = entry.get("lead_id")
            lead = self._leads.get(lead_id)
            contact = self._contacts.get(lead_id)
            if lead is None or contact is None:
                _log.warning(
                    "meetings_seed.json references lead_id=%r not in shim fixture data - skipping entry",
                    lead_id,
                )
                continue

            scheduled_at = None
            raw_scheduled_at = entry.get("scheduled_at")
            if raw_scheduled_at:
                try:
                    scheduled_at = datetime.fromisoformat(raw_scheduled_at.replace("Z", "+00:00"))
                except ValueError:
                    _log.warning("meetings_seed.json entry for %r has an unparseable scheduled_at: %r", lead_id, raw_scheduled_at)

            record = {
                "id": f"meeting_{uuid.uuid4().hex[:8]}",
                "lead_id": lead_id,
                "contact_id": contact["id"],
                "meeting_link": entry.get("meeting_link"),
                "status": "link_sent",
                "scheduled_at": scheduled_at,
                "briefing": entry.get("briefing"),
                "admin_notified": False,
            }
            self._meetings.append(record)
            _log.info("crud(shim): seeded demo meeting for %s from meetings_seed.json", lead["company_name"])

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

    def get_email(self, email_id: str) -> Optional[dict]:
        for e in self._emails:
            if e["id"] == email_id:
                return e
        return None

    def update_email_status(self, email_id: str, status: str) -> Optional[dict]:
        email = self.get_email(email_id)
        if email is not None:
            email["status"] = status
            _log.info("crud(shim): update_email_status email_id=%s status=%s", email_id, status)
        return email

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

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        for m in self._meetings:
            if m["id"] == meeting_id:
                return m
        return None

    def mark_meeting_admin_notified(self, meeting_id: str) -> Optional[dict]:
        meeting = self.get_meeting(meeting_id)
        if meeting is not None:
            meeting["admin_notified"] = True
            _log.info("crud(shim): mark_meeting_admin_notified meeting_id=%s", meeting_id)
        return meeting

    def get_meetings_needing_reminder(self, window_minutes: int = 35) -> list[dict]:
        """Meetings scheduled within the next `window_minutes` that haven't
        had their pre-meeting admin reminder sent yet."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=window_minutes)
        return [
            m
            for m in self._meetings
            if m.get("scheduled_at") is not None
            and not m.get("admin_notified")
            and now <= m["scheduled_at"] <= window_end
        ]

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

    def get_contact_by_email(self, email: str) -> Optional[dict]:
        for contact in self._contacts.values():
            if contact["email"].lower() == email.lower():
                return contact
        return None

    def get_contact(self, contact_id: str) -> Optional[dict]:
        for contact in self._contacts.values():
            if contact["id"] == contact_id:
                return contact
        return None

    def update_lead_stage(self, lead_id: str, stage: str) -> Optional[dict]:
        lead = self._leads.get(lead_id)
        if lead is not None:
            lead["pipeline_stage"] = stage
            _log.info("crud(shim): update_lead_stage lead_id=%s stage=%s", lead_id, stage)
        return lead


crud = _ShimCRUD()
