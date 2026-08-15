"""
Comms-local Firestore adapter — NOT the team's database.

CLAUDE.md and FOLDER_STRUCTURE.md both document the project's database as
PostgreSQL via Supabase, and `backend/db/crud.py` is Wajeeh's file (not
part of sufiyan_work.md). This module does not touch either of those — it
is an optional, comms-scoped alternative to `comms/_shim.py`'s in-memory
`_ShimCRUD`, used only when a Firebase service account key is configured
locally (`FIREBASE_SERVICE_ACCOUNT_PATH`). See conflicts.md for the full
writeup: what this does and doesn't decide about the team's real DB, and
what happens if the team actually adopts Firestore later.

Scope: only the data comms actually owns — emails, replies, meetings,
followups — is read from and written to real Firestore collections.
Leads and contacts stay as local fixture data (same values as
`_shim.py`'s), since real lead/contact ownership belongs to whatever
Wajeeh's actual DB layer turns out to be — this adapter isn't trying to
settle that.

Import this module only when FIREBASE_SERVICE_ACCOUNT_PATH is set —
comms/_deps.py wraps the import in a try/except so a missing/invalid key
or a missing `firebase-admin` install falls back to the in-memory shim
rather than breaking the comms layer.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from comms._shim import get_logger, settings

_log = get_logger("comms.firestore_crud")

USING_FIRESTORE = True

# backend/comms/_firestore_crud.py -> backend/comms -> backend -> repo root
_SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seeds"


def _init_app():
    """Initialize the Firebase Admin app once per process. Raises if the
    configured key path is missing or invalid — comms/_deps.py catches
    this and falls back to the in-memory shim."""
    if not firebase_admin._apps:  # noqa: SLF001 — this is the documented way to check for an existing default app
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()


class _FirestoreCRUD:
    def __init__(self) -> None:
        self._db = _init_app()

        # Same fixture values as _shim.py's _ShimCRUD — kept local rather
        # than in Firestore. See module docstring.
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

        self._seed_demo_meeting()

    # -- demo seed loading (Step 8) — mirrors _shim.py's _seed_demo_meeting,
    # but idempotent: Firestore persists across process runs (unlike the
    # in-memory shim, which starts empty every time), so this checks for
    # an existing document by meeting_link before writing a duplicate.
    def _seed_demo_meeting(self) -> None:
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
                    "meetings_seed.json references lead_id=%r not in fixture data - skipping entry",
                    lead_id,
                )
                continue

            meeting_link = entry.get("meeting_link")
            existing = (
                self._db.collection("meetings")
                .where(filter=FieldFilter("meeting_link", "==", meeting_link))
                .limit(1)
                .get()
            )
            if existing:
                _log.info(
                    "crud(firestore): demo meeting for %s already seeded (meeting_link=%s) - skipping",
                    lead["company_name"],
                    meeting_link,
                )
                continue

            scheduled_at = None
            raw_scheduled_at = entry.get("scheduled_at")
            if raw_scheduled_at:
                try:
                    scheduled_at = datetime.fromisoformat(raw_scheduled_at.replace("Z", "+00:00"))
                except ValueError:
                    _log.warning(
                        "meetings_seed.json entry for %r has an unparseable scheduled_at: %r",
                        lead_id,
                        raw_scheduled_at,
                    )

            doc_id = f"meeting_{uuid.uuid4().hex[:8]}"
            record = {
                "id": doc_id,
                "lead_id": lead_id,
                "contact_id": contact["id"],
                "meeting_link": meeting_link,
                "status": "link_sent",
                "scheduled_at": scheduled_at,
                "briefing": entry.get("briefing"),
                "admin_notified": False,
            }
            self._db.collection("meetings").document(doc_id).set(record)
            _log.info("crud(firestore): seeded demo meeting for %s from meetings_seed.json", lead["company_name"])

    # -- internal helpers -----------------------------------------------
    def _all(self, collection: str) -> list[dict]:
        return [doc.to_dict() for doc in self._db.collection(collection).stream()]

    def _get(self, collection: str, doc_id: str) -> Optional[dict]:
        doc = self._db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None

    # -- emails -----------------------------------------------------------
    def create_email(
        self,
        lead_id: str,
        contact_id: str,
        subject: str,
        body: str,
        status: str,
        sent_at: Optional[datetime] = None,
    ) -> dict:
        doc_id = f"email_{uuid.uuid4().hex[:8]}"
        record = {
            "id": doc_id,
            "lead_id": lead_id,
            "contact_id": contact_id,
            "subject": subject,
            "body": body,
            "status": status,
            "sent_at": sent_at or datetime.now(timezone.utc),
        }
        self._db.collection("emails").document(doc_id).set(record)
        _log.info("crud(firestore): create_email lead_id=%s status=%s", lead_id, status)
        return record

    def get_all_emails(self) -> list[dict]:
        return self._all("emails")

    def get_email(self, email_id: str) -> Optional[dict]:
        return self._get("emails", email_id)

    def update_email_status(self, email_id: str, status: str) -> Optional[dict]:
        ref = self._db.collection("emails").document(email_id)
        if not ref.get().exists:
            return None
        ref.update({"status": status})
        _log.info("crud(firestore): update_email_status email_id=%s status=%s", email_id, status)
        return ref.get().to_dict()

    def get_emails_needing_followup(self, days: int = 3) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        replied_email_ids = {r["email_id"] for r in self._all("replies")}
        followed_up_email_ids = {f["email_id"] for f in self._all("followups")}
        return [
            e
            for e in self.get_all_emails()
            if e["status"] == "sent"
            and e["sent_at"] <= cutoff
            and e["id"] not in replied_email_ids
            and e["id"] not in followed_up_email_ids
        ]

    # -- replies ------------------------------------------------------------
    def create_reply(self, email_id: str, raw_body: str, received_at: Optional[datetime] = None) -> dict:
        doc_id = f"reply_{uuid.uuid4().hex[:8]}"
        record = {
            "id": doc_id,
            "email_id": email_id,
            "raw_body": raw_body,
            "received_at": received_at or datetime.now(timezone.utc),
        }
        self._db.collection("replies").document(doc_id).set(record)
        _log.info("crud(firestore): create_reply email_id=%s", email_id)
        return record

    # -- meetings ---------------------------------------------------------
    def create_meeting(
        self,
        lead_id: str,
        contact_id: str,
        meeting_link: str,
        status: str = "link_sent",
        scheduled_at: Optional[datetime] = None,
        briefing: Optional[dict] = None,
    ) -> dict:
        doc_id = f"meeting_{uuid.uuid4().hex[:8]}"
        record = {
            "id": doc_id,
            "lead_id": lead_id,
            "contact_id": contact_id,
            "meeting_link": meeting_link,
            "status": status,
            "scheduled_at": scheduled_at,
            "briefing": briefing,
            "admin_notified": False,
        }
        self._db.collection("meetings").document(doc_id).set(record)
        _log.info("crud(firestore): create_meeting lead_id=%s link=%s", lead_id, meeting_link)
        return record

    def get_all_meetings(self) -> list[dict]:
        return self._all("meetings")

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        return self._get("meetings", meeting_id)

    def mark_meeting_admin_notified(self, meeting_id: str) -> Optional[dict]:
        ref = self._db.collection("meetings").document(meeting_id)
        if not ref.get().exists:
            return None
        ref.update({"admin_notified": True})
        _log.info("crud(firestore): mark_meeting_admin_notified meeting_id=%s", meeting_id)
        return ref.get().to_dict()

    def get_meetings_needing_reminder(self, window_minutes: int = 35) -> list[dict]:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=window_minutes)
        return [
            m
            for m in self.get_all_meetings()
            if m.get("scheduled_at") is not None
            and not m.get("admin_notified")
            and now <= m["scheduled_at"] <= window_end
        ]

    # -- follow-ups --------------------------------------------------------
    def create_followup(self, lead_id: str, email_id: str, scheduled_for: datetime, status: str = "sent") -> dict:
        doc_id = f"followup_{uuid.uuid4().hex[:8]}"
        record = {
            "id": doc_id,
            "lead_id": lead_id,
            "email_id": email_id,
            "scheduled_for": scheduled_for,
            "status": status,
        }
        self._db.collection("followups").document(doc_id).set(record)
        _log.info("crud(firestore): create_followup lead_id=%s", lead_id)
        return record

    # -- leads / contacts (local fixtures — see module docstring) ---------
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
            _log.info("crud(firestore): update_lead_stage lead_id=%s stage=%s", lead_id, stage)
        return lead


crud = _FirestoreCRUD()
