"""Document shapes and the enum-ish constants shared across the codebase.

Persistence is Firestore, so there is no ORM here — a "model" is just a dict
with a known set of keys. These factories exist so every writer produces the
same shape, and so defaults live in one place.

Collections mirror the relational layout (leads, contacts, emails, replies,
meetings, followups, pipeline_events) with `lead_id` / `email_id` fields
rather than nesting, which keeps the queries simple.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

# ── Enum-ish string constants ────────────────────────────────────────

PIPELINE_STAGES = [
    "Discovered",
    "Potential",
    "Researching",
    "Qualified",
    "Contacted",
    "Interested",
    "Meeting Scheduled",
    "Converted",
    "Not Qualified",
    "Not Interested",
    "Do Not Contact",
]

ACTIVE_STAGES = PIPELINE_STAGES[:8]
REJECTED_STAGES = PIPELINE_STAGES[8:]

EMAIL_STATUSES = ["draft", "sent", "failed", "replied"]
MEETING_STATUSES = ["link_sent", "confirmed", "completed", "cancelled"]
FOLLOWUP_STATUSES = ["pending", "sent", "cancelled"]
CLASSIFICATIONS = [
    "Interested",
    "Pricing Objection",
    "Not Interested",
    "Meeting Requested",
    "Out of Office",
    "Unclear",
]


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── Document factories ───────────────────────────────────────────────
# Every field is written explicitly, including the None ones, so a document
# read back always has the full key set and callers never need .get() guards.

LEAD_FIELDS = {
    "company_name", "website", "industry", "location", "employee_count",
    "pipeline_stage", "lead_score", "score_explanation", "recommended_service",
    "pitch_angle", "icp_fit", "research_summary", "apollo_data", "session_id",
}

CONTACT_FIELDS = {"name", "role", "email", "linkedin_url", "is_primary"}


def lead_doc(data: dict[str, Any], doc_id: str | None = None) -> dict[str, Any]:
    return {
        "id": doc_id or data.get("id") or new_id(),
        "company_name": data.get("company_name"),
        "website": data.get("website"),
        "industry": data.get("industry"),
        "location": data.get("location"),
        "employee_count": data.get("employee_count"),
        "pipeline_stage": data.get("pipeline_stage") or "Discovered",
        "lead_score": data.get("lead_score"),
        "score_explanation": data.get("score_explanation"),
        "recommended_service": data.get("recommended_service"),
        "pitch_angle": data.get("pitch_angle"),
        "icp_fit": data.get("icp_fit"),
        "research_summary": data.get("research_summary"),
        "apollo_data": data.get("apollo_data"),
        "session_id": data.get("session_id"),
        "created_at": data.get("created_at") or now(),
        "updated_at": data.get("updated_at") or now(),
    }


def contact_doc(
    data: dict[str, Any], lead_id: str, doc_id: str | None = None
) -> dict[str, Any]:
    return {
        "id": doc_id or data.get("id") or new_id(),
        "lead_id": lead_id,
        "name": data.get("name"),
        "role": data.get("role"),
        "email": data.get("email"),
        "linkedin_url": data.get("linkedin_url"),
        "is_primary": bool(data.get("is_primary", False)),
        "created_at": data.get("created_at") or now(),
    }


def email_doc(
    lead_id: str,
    contact_id: str | None,
    subject: str | None,
    body: str | None,
    status: str = "draft",
    sent_at: datetime | None = None,
    doc_id: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "contact_id": contact_id,
        "subject": subject,
        "body": body,
        "status": status,
        "sent_at": sent_at or (now() if status == "sent" else None),
        "created_at": created_at or now(),
    }


def reply_doc(
    email_id: str,
    raw_body: str | None,
    classification: str | None = None,
    summary: str | None = None,
    next_action: str | None = None,
    received_at: datetime | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id or new_id(),
        "email_id": email_id,
        "raw_body": raw_body,
        "classification": classification,
        "summary": summary,
        "next_action": next_action,
        "received_at": received_at or now(),
    }


def meeting_doc(
    lead_id: str,
    contact_id: str | None,
    meeting_link: str | None,
    scheduled_at: datetime | None = None,
    briefing: dict | None = None,
    status: str = "link_sent",
    admin_notified: bool = False,
    doc_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "contact_id": contact_id,
        "meeting_link": meeting_link,
        "scheduled_at": scheduled_at,
        "briefing": briefing,
        "admin_notified": admin_notified,
        "status": status,
        "created_at": now(),
    }


def followup_doc(
    lead_id: str,
    original_email_id: str,
    scheduled_for: datetime | None = None,
    status: str = "pending",
    followup_email_id: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "original_email_id": original_email_id,
        "followup_email_id": followup_email_id,
        "scheduled_for": scheduled_for,
        "status": status,
        "created_at": now(),
    }


def event_doc(
    lead_id: str,
    from_stage: str | None,
    to_stage: str | None,
    reason: str | None = None,
    created_at: datetime | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "reason": reason,
        "created_at": created_at or now(),
    }
