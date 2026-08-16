"""Every database operation in the project, against Firestore.

These functions are **synchronous**, because the Firestore Admin SDK is.
That is deliberate: the comms layer runs inside APScheduler jobs which
cannot await, and Sufiyan's routers call `crud.x()` directly. FastAPI route
handlers use `db/acrud.py`, which wraps each of these in a thread so the
event loop is never blocked.

Two naming conventions are exported on purpose:

  * the names Sufiyan's comms layer codes against — `get_meetings_needing_
    reminder`, `mark_meeting_admin_notified`, `get_contact` — with exactly
    the signatures in `comms/_shim.py`, so nothing in comms/ needed editing;
  * the richer names my routes and memory layer use — `get_all_leads`,
    `upsert_leads_from_pipeline`, `count_leads_by_stage`, and friends.

Every function returns plain dicts (or None), never SDK document objects.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from config.settings import settings
from db import firestore as fs
from db.models import (
    CONTACT_FIELDS,
    LEAD_FIELDS,
    autopsy_doc,
    contact_doc,
    email_doc,
    event_doc,
    followup_doc,
    lead_doc,
    meeting_doc,
    new_id,
    reply_doc,
    verdict_doc,
)
from utils.logger import get_logger

log = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── low-level helpers ────────────────────────────────────────────────

def _set(collection: str, doc: dict[str, Any]) -> dict[str, Any]:
    fs.collection(collection).document(doc["id"]).set(doc)
    return doc


def _get(collection: str, doc_id: str | None) -> dict | None:
    if not doc_id:
        return None
    snap = fs.collection(collection).document(doc_id).get()
    return snap.to_dict() if snap.exists else None


def _all(collection: str) -> list[dict]:
    return [d.to_dict() for d in fs.collection(collection).stream()]


def _where(collection: str, field: str, value: Any) -> list[dict]:
    """Single-field equality query.

    Firestore's composite filters need matching indexes, and the dataset here
    is small, so anything more complex is filtered in Python instead — one
    indexed lookup, then plain list comprehensions.
    """
    query = fs.collection(collection).where(filter=FieldFilter(field, "==", value))
    return [d.to_dict() for d in query.stream()]


def _patch(collection: str, doc_id: str, updates: dict[str, Any]) -> dict | None:
    ref = fs.collection(collection).document(doc_id)
    snap = ref.get()
    if not snap.exists:
        return None
    ref.update(updates)
    merged = {**snap.to_dict(), **updates}
    return merged


def _as_dt(value: Any) -> datetime | None:
    """Firestore hands timestamps back as tz-aware datetimes; be tolerant of
    strings (from seed files) and naive values so comparisons never explode."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # google.api_core DatetimeWithNanoseconds and friends
    try:
        return value.replace(tzinfo=value.tzinfo or timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _sorted(rows: list[dict], key: str, reverse: bool = False) -> list[dict]:
    """Sort by a datetime field, tolerating missing values (they sink)."""
    floor = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(rows, key=lambda r: _as_dt(r.get(key)) or floor, reverse=reverse)


def _clamp_score(score: Any) -> int | None:
    if score is None:
        return None
    try:
        return max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError):
        return None


# ══════════════════════════════════════════════════════════════════════
# LEADS
# ══════════════════════════════════════════════════════════════════════

def create_lead(lead_dict: dict[str, Any]) -> dict:
    """Insert a lead and log its arrival on the timeline."""
    doc = lead_doc(lead_dict)
    doc["lead_score"] = _clamp_score(doc["lead_score"])
    _set(fs.LEADS, doc)
    _set(
        fs.PIPELINE_EVENTS,
        event_doc(doc["id"], None, doc["pipeline_stage"], "Lead discovered"),
    )
    log.info("created lead %s (%s)", doc["company_name"], doc["id"])
    return doc


def get_lead(lead_id: str) -> dict | None:
    return _get(fs.LEADS, lead_id)


def get_all_leads(session_id: str | None = None) -> list[dict]:
    """All leads, newest first. Pass session_id to scope to one run."""
    rows = _where(fs.LEADS, "session_id", session_id) if session_id else _all(fs.LEADS)
    return _sorted(rows, "created_at", reverse=True)


def get_lead_by_company(
    company_name: str, session_id: str | None = None
) -> dict | None:
    """Case-insensitive lookup — used to dedupe across pipeline passes."""
    target = (company_name or "").strip().lower()
    for row in get_all_leads(session_id):
        if (row.get("company_name") or "").strip().lower() == target:
            return row
    return None


def update_lead_stage(
    lead_id: str, stage: str, reason: str | None = None
) -> dict | None:
    """Move a lead to a new stage and record the transition."""
    lead = get_lead(lead_id)
    if lead is None:
        log.warning("update_lead_stage: lead %s not found", lead_id)
        return None

    old_stage = lead.get("pipeline_stage")
    if old_stage == stage:
        return lead

    updated = _patch(fs.LEADS, lead_id, {"pipeline_stage": stage, "updated_at": _now()})
    _set(
        fs.PIPELINE_EVENTS,
        event_doc(lead_id, old_stage, stage, reason or "Stage updated"),
    )
    log.info("lead %s: %s -> %s", lead.get("company_name"), old_stage, stage)
    return updated


def update_lead(lead_id: str, updates: dict[str, Any]) -> dict | None:
    """Partial update. A stage change here still writes a timeline event."""
    lead = get_lead(lead_id)
    if lead is None:
        return None

    clean = {k: v for k, v in updates.items() if k in LEAD_FIELDS}
    if "lead_score" in clean:
        clean["lead_score"] = _clamp_score(clean["lead_score"])

    new_stage = clean.pop("pipeline_stage", None)
    if clean:
        clean["updated_at"] = _now()
        lead = _patch(fs.LEADS, lead_id, clean) or lead

    if new_stage and new_stage != lead.get("pipeline_stage"):
        lead = update_lead_stage(lead_id, new_stage, "Updated manually") or lead

    return lead


def update_lead_score(
    lead_id: str, score: int, explanation: str | None = None
) -> dict | None:
    updates: dict[str, Any] = {"lead_score": _clamp_score(score), "updated_at": _now()}
    if explanation is not None:
        updates["score_explanation"] = explanation
    return _patch(fs.LEADS, lead_id, updates)


def update_lead_research(
    lead_id: str,
    research_summary: str | None = None,
    apollo_data: dict | None = None,
) -> dict | None:
    updates: dict[str, Any] = {"updated_at": _now()}
    if research_summary is not None:
        updates["research_summary"] = research_summary
    if apollo_data is not None:
        updates["apollo_data"] = apollo_data
    return _patch(fs.LEADS, lead_id, updates)


def update_lead_service(
    lead_id: str,
    recommended_service: str | None = None,
    pitch_angle: str | None = None,
) -> dict | None:
    updates: dict[str, Any] = {"updated_at": _now()}
    if recommended_service is not None:
        updates["recommended_service"] = recommended_service
    if pitch_angle is not None:
        updates["pitch_angle"] = pitch_angle
    return _patch(fs.LEADS, lead_id, updates)


def delete_lead(lead_id: str) -> bool:
    """Remove a lead and everything hanging off it (no cascades in Firestore)."""
    if get_lead(lead_id) is None:
        return False

    for collection in (
        fs.CONTACTS,
        fs.EMAILS,
        fs.MEETINGS,
        fs.FOLLOWUPS,
        fs.PIPELINE_EVENTS,
        fs.VERDICTS,
        fs.AUTOPSIES,
    ):
        for row in _where(collection, "lead_id", lead_id):
            if collection == fs.EMAILS:
                for reply in _where(fs.REPLIES, "email_id", row["id"]):
                    fs.collection(fs.REPLIES).document(reply["id"]).delete()
            fs.collection(collection).document(row["id"]).delete()

    fs.collection(fs.LEADS).document(lead_id).delete()
    log.info("deleted lead %s", lead_id)
    return True


# PIPELINE_TO_LEAD maps the agent state's key names onto LEAD_FIELDS.
# The agents and this schema grew up apart: combined_processing_agent writes
# `score`/`explanation` and discovery writes `url`, while a lead document
# stores `lead_score`/`score_explanation`/`website`. Without this translation
# the filter in upsert_leads_from_pipeline drops every one of them, and a run
# that qualified leads and wrote emails still lands in Firestore as
# "Discovered, Unscored, no contacts" — which is exactly how it behaved.
PIPELINE_TO_LEAD = {
    "score": "lead_score",
    "explanation": "score_explanation",
    "url": "website",
    "why_it_fits": "pitch_angle",
}


def _lead_fields_from_pipeline(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate one pipeline lead dict into LEAD_FIELDS-shaped values."""
    fields = {k: v for k, v in raw.items() if k in LEAD_FIELDS}
    for src, dest in PIPELINE_TO_LEAD.items():
        if fields.get(dest) in (None, "") and raw.get(src) not in (None, ""):
            fields[dest] = raw[src]
    return fields


def _stage_for(raw: dict[str, Any], fields: dict[str, Any]) -> str | None:
    """Where a lead belongs on the board, given what the pipeline learned.

    Only inferred when the pipeline did not set a stage itself. A scored lead
    has been through qualification, so leaving it at the default "Discovered"
    would show every finished run as an untouched board.
    """
    if raw.get("pipeline_stage"):
        return raw["pipeline_stage"]

    score = fields.get("lead_score")
    if score is None:
        return None
    if score < settings.MIN_QUALIFICATION_SCORE:
        return "Not Qualified"
    return "Qualified"


def upsert_leads_from_pipeline(
    leads_list: list[dict[str, Any]], session_id: str
) -> list[dict]:
    """Bulk-write the pipeline's outreach queue.

    Dedupes on company_name within the session, so calling this after each
    graph node updates leads in place rather than duplicating them. A
    "contacts" list on a lead dict is upserted by email, and the single
    `primary_contact` the agents produce is treated as one.
    """
    saved: list[dict] = []
    seen_ids: set[str] = set()

    for raw in leads_list:
        name = (raw.get("company_name") or "").strip()
        if not name:
            log.warning("skipping lead with no company_name")
            continue

        fields = _lead_fields_from_pipeline(raw)
        fields["company_name"] = name
        fields["session_id"] = session_id
        if "lead_score" in fields:
            fields["lead_score"] = _clamp_score(fields["lead_score"])
        stage = _stage_for(raw, fields)
        if stage:
            fields["pipeline_stage"] = stage

        existing = get_lead_by_company(name, session_id)

        if existing is None:
            doc = lead_doc(fields, doc_id=raw.get("id"))
            _set(fs.LEADS, doc)
            _set(
                fs.PIPELINE_EVENTS,
                event_doc(doc["id"], None, doc["pipeline_stage"], "Lead discovered"),
            )
        else:
            new_stage = fields.pop("pipeline_stage", None)
            changes = {k: v for k, v in fields.items() if v is not None}
            changes["updated_at"] = _now()
            doc = _patch(fs.LEADS, existing["id"], changes) or existing
            if new_stage and new_stage != doc.get("pipeline_stage"):
                doc = update_lead_stage(doc["id"], new_stage, "Advanced by pipeline") or doc

        # The agents attach one chosen decision maker as `primary_contact`;
        # older callers pass a `contacts` list. Accept both.
        contacts = list(raw.get("contacts") or [])
        primary = raw.get("primary_contact")
        if isinstance(primary, dict) and primary.get("email"):
            contacts.append({**primary, "is_primary": True})

        contact_id = None
        for contact in contacts:
            saved_contact = create_contact(contact, doc["id"])
            if contact_id is None and saved_contact:
                contact_id = saved_contact.get("id")

        # Persist the drafted outreach as a draft email. Without this the
        # subject/body the pipeline wrote exist only in the run's state, so
        # the UI has nothing to show and nothing to send — which is why a
        # completed run looked like it had produced no outreach at all.
        subject = (raw.get("subject") or "").strip()
        body = (raw.get("body") or "").strip()
        if subject and body and not get_emails_for_lead(doc["id"]):
            create_email(doc["id"], contact_id, subject, body, "draft")

        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            saved.append(doc)

    log.info("upserted %s leads for session %s", len(saved), session_id)
    return saved


def count_leads_by_stage(session_id: str | None = None) -> dict[str, int]:
    """{stage: count} — powers the status endpoint and Kanban badges."""
    counts: dict[str, int] = {}
    for lead in get_all_leads(session_id):
        stage = lead.get("pipeline_stage") or "Discovered"
        counts[stage] = counts.get(stage, 0) + 1
    return counts


# ══════════════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════════════

def create_contact(contact_dict: dict[str, Any], lead_id: str) -> dict:
    """Insert or update a contact, matched on email within the lead."""
    fields = {k: v for k, v in contact_dict.items() if k in CONTACT_FIELDS}
    email = fields.get("email")

    if email:
        for existing in _where(fs.CONTACTS, "lead_id", lead_id):
            if (existing.get("email") or "").lower() == email.lower():
                changes = {k: v for k, v in fields.items() if v is not None}
                return _patch(fs.CONTACTS, existing["id"], changes) or existing

    doc = contact_doc(fields, lead_id, doc_id=contact_dict.get("id"))
    return _set(fs.CONTACTS, doc)


def get_contact(contact_id: str) -> dict | None:
    return _get(fs.CONTACTS, contact_id)


def get_contacts_for_lead(lead_id: str) -> list[dict]:
    """Contacts for a lead, primary first."""
    rows = _where(fs.CONTACTS, "lead_id", lead_id)
    rows = _sorted(rows, "created_at")
    return sorted(rows, key=lambda c: not c.get("is_primary", False))


def get_primary_contact(lead_id: str) -> dict | None:
    """The flagged primary contact, falling back to the first one found."""
    contacts = get_contacts_for_lead(lead_id)
    return contacts[0] if contacts else None


def get_contact_by_email(email: str) -> dict | None:
    """Used by the inbound reply webhook to match a sender to a contact."""
    if not email:
        return None
    target = email.strip().lower()
    for row in _all(fs.CONTACTS):
        if (row.get("email") or "").strip().lower() == target:
            return row
    return None


# ══════════════════════════════════════════════════════════════════════
# EMAILS
# ══════════════════════════════════════════════════════════════════════

def create_email(
    lead_id: str,
    contact_id: Optional[str],
    subject: str,
    body: str,
    status: str = "draft",
    sent_at: Optional[datetime] = None,
) -> dict:
    doc = email_doc(lead_id, contact_id, subject, body, status, sent_at)
    _set(fs.EMAILS, doc)
    log.info("email %s for lead %s (status=%s)", doc["id"], lead_id, status)
    return doc


def get_email(email_id: str) -> dict | None:
    return _get(fs.EMAILS, email_id)


def get_all_emails() -> list[dict]:
    return _sorted(_all(fs.EMAILS), "created_at", reverse=True)


def get_emails_for_lead(lead_id: str) -> list[dict]:
    return _sorted(_where(fs.EMAILS, "lead_id", lead_id), "created_at")


def update_email_status(email_id: str, status: str) -> dict | None:
    updates: dict[str, Any] = {"status": status}
    current = get_email(email_id)
    if current is None:
        return None
    if status == "sent" and current.get("sent_at") is None:
        updates["sent_at"] = _now()
    return _patch(fs.EMAILS, email_id, updates)


def get_emails_needing_followup(days: int = 3) -> list[dict]:
    """Sent more than `days` ago, never replied to, no follow-up queued.

    Done in Python rather than as a compound query: Firestore has no NOT-IN
    across collections, and the "no reply exists" test is a join.
    """
    cutoff = _now() - timedelta(days=days)

    replied_to = {r.get("email_id") for r in _all(fs.REPLIES)}
    followed_up = {
        f.get("original_email_id")
        for f in _all(fs.FOLLOWUPS)
        if f.get("status") in ("sent", "pending")
    }

    due = []
    for email in _all(fs.EMAILS):
        sent_at = _as_dt(email.get("sent_at"))
        if (
            email.get("status") == "sent"
            and sent_at is not None
            and sent_at <= cutoff
            and email["id"] not in replied_to
            and email["id"] not in followed_up
        ):
            due.append(email)

    if due:
        log.info("%s emails are due a follow-up", len(due))
    return _sorted(due, "sent_at")


def find_email_by_subject(
    subject: str, contact_id: str | None = None
) -> dict | None:
    """Match an inbound 'Re: ...' back to the email that was sent.

    The caller strips the Re:/Fwd: prefix first.
    """
    target = (subject or "").strip().lower()
    candidates = [
        e
        for e in _all(fs.EMAILS)
        if (e.get("subject") or "").strip().lower() == target
        and e.get("status") in ("sent", "replied")
        and (contact_id is None or e.get("contact_id") == contact_id)
    ]
    candidates = _sorted(candidates, "sent_at", reverse=True)
    return candidates[0] if candidates else None


# ══════════════════════════════════════════════════════════════════════
# REPLIES
# ══════════════════════════════════════════════════════════════════════

def create_reply(
    email_id: str,
    raw_body: str,
    received_at: Optional[datetime] = None,
    classification: str | None = None,
    summary: str | None = None,
    next_action: str | None = None,
) -> dict:
    """Record an inbound reply and flip the parent email to 'replied'.

    Argument order matches comms/_shim.py — `received_at` third — so the
    comms layer's positional calls keep working.
    """
    doc = reply_doc(
        email_id, raw_body, classification, summary, next_action, received_at
    )
    _set(fs.REPLIES, doc)
    _patch(fs.EMAILS, email_id, {"status": "replied"})
    log.info("reply on email %s classified as %s", email_id, classification)
    return doc


def update_reply_classification(
    reply_id: str,
    classification: str,
    summary: str | None = None,
    next_action: str | None = None,
) -> dict | None:
    updates: dict[str, Any] = {"classification": classification}
    if summary is not None:
        updates["summary"] = summary
    if next_action is not None:
        updates["next_action"] = next_action
    return _patch(fs.REPLIES, reply_id, updates)


def get_all_replies() -> list[dict]:
    return _sorted(_all(fs.REPLIES), "received_at", reverse=True)


def get_replies_for_lead(lead_id: str) -> list[dict]:
    email_ids = {e["id"] for e in _where(fs.EMAILS, "lead_id", lead_id)}
    rows = [r for r in _all(fs.REPLIES) if r.get("email_id") in email_ids]
    return _sorted(rows, "received_at", reverse=True)


# ══════════════════════════════════════════════════════════════════════
# MEETINGS
# ══════════════════════════════════════════════════════════════════════

def create_meeting(
    lead_id: str,
    contact_id: Optional[str],
    meeting_link: Optional[str],
    status: str = "link_sent",
    scheduled_at: Optional[datetime] = None,
    briefing: Optional[dict] = None,
) -> dict:
    doc = meeting_doc(lead_id, contact_id, meeting_link, scheduled_at, briefing, status)
    _set(fs.MEETINGS, doc)
    log.info("meeting %s booked for lead %s", doc["id"], lead_id)
    return doc


def get_meeting(meeting_id: str) -> dict | None:
    return _get(fs.MEETINGS, meeting_id)


def get_all_meetings() -> list[dict]:
    """Meetings soonest first; unscheduled ones sink to the bottom."""
    rows = _all(fs.MEETINGS)
    far_future = datetime.max.replace(tzinfo=timezone.utc)
    return sorted(rows, key=lambda m: _as_dt(m.get("scheduled_at")) or far_future)


def get_meetings_for_lead(lead_id: str) -> list[dict]:
    return _sorted(_where(fs.MEETINGS, "lead_id", lead_id), "scheduled_at")


def get_meetings_needing_reminder(window_minutes: int = 35) -> list[dict]:
    """Meetings starting soon the admin has not been alerted about."""
    now = _now()
    window_end = now + timedelta(minutes=window_minutes)

    due = []
    for meeting in _all(fs.MEETINGS):
        scheduled = _as_dt(meeting.get("scheduled_at"))
        if (
            scheduled is not None
            and not meeting.get("admin_notified")
            and now <= scheduled <= window_end
            and meeting.get("status") in ("link_sent", "confirmed")
        ):
            due.append(meeting)
    return _sorted(due, "scheduled_at")


def mark_meeting_admin_notified(meeting_id: str) -> dict | None:
    return _patch(fs.MEETINGS, meeting_id, {"admin_notified": True})


def update_meeting_briefing(meeting_id: str, briefing: dict) -> dict | None:
    return _patch(fs.MEETINGS, meeting_id, {"briefing": briefing})


def update_meeting_status(meeting_id: str, status: str) -> dict | None:
    return _patch(fs.MEETINGS, meeting_id, {"status": status})


# Aliases kept so older call sites in my routes keep working.
get_upcoming_meetings_needing_reminder = get_meetings_needing_reminder
update_meeting_admin_notified = mark_meeting_admin_notified


# ══════════════════════════════════════════════════════════════════════
# FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════════

def create_followup(
    lead_id: str,
    email_id: str,
    scheduled_for: Optional[datetime] = None,
    status: str = "pending",
) -> dict:
    """`email_id` is the ORIGINAL email being followed up on."""
    doc = followup_doc(lead_id, email_id, scheduled_for, status)
    return _set(fs.FOLLOWUPS, doc)


def get_pending_followups() -> list[dict]:
    rows = [f for f in _all(fs.FOLLOWUPS) if f.get("status") == "pending"]
    return _sorted(rows, "scheduled_for")


def update_followup_sent(followup_id: str, followup_email_id: str) -> dict | None:
    return _patch(
        fs.FOLLOWUPS,
        followup_id,
        {"followup_email_id": followup_email_id, "status": "sent"},
    )


# ══════════════════════════════════════════════════════════════════════
# PIPELINE EVENTS
# ══════════════════════════════════════════════════════════════════════

def create_event(
    lead_id: str,
    from_stage: str | None,
    to_stage: str | None,
    reason: str | None = None,
) -> dict:
    return _set(fs.PIPELINE_EVENTS, event_doc(lead_id, from_stage, to_stage, reason))


def get_events_for_lead(lead_id: str) -> list[dict]:
    """Timeline for a lead, oldest first."""
    return _sorted(_where(fs.PIPELINE_EVENTS, "lead_id", lead_id), "created_at")


# ══════════════════════════════════════════════════════════════════════
# DEVIL'S ADVOCATE VERDICTS
# ══════════════════════════════════════════════════════════════════════

def create_verdict(lead_id: str, debate: dict[str, Any]) -> dict:
    """Store one resolved debate. Re-running a lead adds a document rather
    than replacing the last one, so the earlier verdicts stay as history."""
    doc = verdict_doc(
        lead_id=lead_id,
        prosecution=debate.get("prosecution") or [],
        defense=debate.get("defense") or [],
        prosecution_closing=debate.get("prosecution_closing"),
        defense_closing=debate.get("defense_closing"),
        winner=debate.get("winner"),
        confidence=_clamp_score(debate.get("confidence")),
        reasoning=debate.get("reasoning"),
        decisive_argument=debate.get("decisive_argument"),
        evidence_strength=debate.get("evidence_strength"),
    )
    _set(fs.VERDICTS, doc)
    log.info(
        "verdict for lead %s: %s wins at %s%%",
        lead_id, doc["winner"], doc["confidence"],
    )
    return doc


def get_latest_verdict(lead_id: str) -> dict | None:
    """The most recent debate for a lead, or None if it has never been run."""
    rows = _sorted(_where(fs.VERDICTS, "lead_id", lead_id), "created_at", reverse=True)
    return rows[0] if rows else None


# ══════════════════════════════════════════════════════════════════════
# DEAL AUTOPSIES
# ══════════════════════════════════════════════════════════════════════

def create_autopsy(lead_id: str, findings: dict[str, Any]) -> dict:
    """Store one post-mortem, same append-only treatment as verdicts."""
    doc = autopsy_doc(
        lead_id=lead_id,
        cause_of_death=findings.get("cause_of_death"),
        cause_evidence=findings.get("cause_evidence"),
        misfire=findings.get("misfire"),
        misfire_tag=findings.get("misfire_tag"),
        correction=findings.get("correction"),
        icp_adjustment=findings.get("icp_adjustment"),
        confidence=_clamp_score(findings.get("confidence")),
        engagement_stats=findings.get("engagement_stats"),
        final_stage=findings.get("final_stage"),
    )
    _set(fs.AUTOPSIES, doc)
    log.info("autopsy for lead %s: %s", lead_id, doc["cause_of_death"])
    return doc


def get_latest_autopsy(lead_id: str) -> dict | None:
    rows = _sorted(_where(fs.AUTOPSIES, "lead_id", lead_id), "created_at", reverse=True)
    return rows[0] if rows else None


def get_all_autopsies() -> list[dict]:
    """Every post-mortem, newest first — the input to the insights rollup."""
    return _sorted(_all(fs.AUTOPSIES), "created_at", reverse=True)


# ══════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ══════════════════════════════════════════════════════════════════════

def clear_all() -> None:
    """Wipe every collection. Dev only — used by load_seeds.py."""
    client = fs.get_client()
    for collection in fs.ALL_COLLECTIONS:
        for doc in client.collection(collection).stream():
            doc.reference.delete()
    log.warning("cleared all collections")


__all__ = [name for name in dir() if not name.startswith("_")]
