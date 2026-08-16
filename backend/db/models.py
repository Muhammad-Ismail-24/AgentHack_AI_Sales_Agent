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

CONTACT_FIELDS = {"name", "role", "email", "linkedin_url", "is_primary", "phone"}


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
        "phone": data.get("phone"),
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


# ── Intelligence layer ───────────────────────────────────────────────
# Written by the on-demand agents, not by the pipeline. Both are keyed on
# lead_id and only the newest per lead is ever read back, so re-running one
# leaves the earlier document in place as history.

# Which side the judge ruled for.
VERDICT_WINNERS = ["prosecution", "defence"]
EVIDENCE_STRENGTHS = ["high", "medium", "low"]

# Machine-read by the autopsy insights endpoint to reweight the next run.
# The prompt hands the model this exact list to choose from.
MISFIRE_TAGS = [
    "wrong_service",
    "wrong_persona",
    "wrong_timing",
    "slow_response",
    "weak_personalisation",
    "no_engagement",
    "price",
]


def verdict_doc(
    lead_id: str,
    prosecution: list[dict[str, Any]],
    defense: list[dict[str, Any]],
    prosecution_closing: str | None,
    defense_closing: str | None,
    winner: str | None,
    confidence: int | None,
    reasoning: str | None,
    decisive_argument: str | None,
    evidence_strength: str | None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """One resolved Devil's Advocate debate over a lead."""
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "prosecution": prosecution,
        "defense": defense,
        "prosecution_closing": prosecution_closing,
        "defense_closing": defense_closing,
        "winner": winner,
        "confidence": confidence,
        "reasoning": reasoning,
        "decisive_argument": decisive_argument,
        "evidence_strength": evidence_strength,
        "created_at": now(),
    }


def autopsy_doc(
    lead_id: str,
    cause_of_death: str | None,
    cause_evidence: str | None,
    misfire: str | None,
    misfire_tag: str | None,
    correction: str | None,
    icp_adjustment: str | None,
    confidence: int | None,
    engagement_stats: dict[str, Any] | None = None,
    final_stage: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """The post-mortem on one dead lead."""
    return {
        "id": doc_id or new_id(),
        "lead_id": lead_id,
        "cause_of_death": cause_of_death,
        "cause_evidence": cause_evidence,
        "misfire": misfire,
        "misfire_tag": misfire_tag,
        "correction": correction,
        "icp_adjustment": icp_adjustment,
        "confidence": confidence,
        "engagement_stats": engagement_stats or {},
        "final_stage": final_stage,
        "created_at": now(),
    }
