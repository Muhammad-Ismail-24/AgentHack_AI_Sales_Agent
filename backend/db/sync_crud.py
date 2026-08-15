"""Synchronous CRUD facade for code that cannot await.

The comms layer runs inside APScheduler jobs, which are synchronous. Rather
than forcing an event loop in there, this module mirrors the subset of
db/crud.py that comms needs, on a sync session, returning plain dicts.

The signatures here match `backend/comms/_shim.py` exactly (see conflicts.md
section 2), so merging the comms branch is a one-line change in
`backend/comms/_deps.py`:

    from db import sync_crud as crud

Async code must use db/crud.py instead — this module is not the source of
truth for business logic, it only re-expresses it for sync callers.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.database import SyncSessionLocal
from db.models import (
    Contact,
    Email,
    FollowUp,
    Lead,
    Meeting,
    PipelineEvent,
    Reply,
)
from utils.logger import get_logger

log = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(obj: Any) -> dict[str, Any] | None:
    """Flatten a model instance to a plain dict of its own columns."""
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _session() -> Session:
    return SyncSessionLocal()


# ── LEADS ────────────────────────────────────────────────────────────

def get_lead(lead_id: str) -> dict | None:
    with _session() as db:
        return _to_dict(db.get(Lead, lead_id))


def update_lead_stage(lead_id: str, stage: str, reason: str | None = None) -> dict | None:
    """Move a lead's stage and record the transition, same as async crud."""
    with _session() as db:
        lead = db.get(Lead, lead_id)
        if lead is None:
            log.warning("update_lead_stage: lead %s not found", lead_id)
            return None
        if lead.pipeline_stage != stage:
            db.add(
                PipelineEvent(
                    lead_id=lead.id,
                    from_stage=lead.pipeline_stage,
                    to_stage=stage,
                    reason=reason or "Updated by comms",
                )
            )
            lead.pipeline_stage = stage
            db.commit()
            db.refresh(lead)
        return _to_dict(lead)


# ── CONTACTS ─────────────────────────────────────────────────────────

def get_primary_contact(lead_id: str) -> dict | None:
    with _session() as db:
        contact = db.execute(
            select(Contact)
            .where(Contact.lead_id == lead_id)
            .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
        ).scalars().first()
        return _to_dict(contact)


def get_contact_by_email(email: str) -> dict | None:
    with _session() as db:
        contact = db.execute(
            select(Contact).where(func.lower(Contact.email) == email.lower())
        ).scalars().first()
        return _to_dict(contact)


# ── EMAILS ───────────────────────────────────────────────────────────

def create_email(
    lead_id: str,
    contact_id: str | None,
    subject: str,
    body: str,
    status: str = "draft",
    sent_at: datetime | None = None,
) -> dict:
    with _session() as db:
        email = Email(
            lead_id=lead_id,
            contact_id=contact_id,
            subject=subject,
            body=body,
            status=status,
            sent_at=sent_at or (_now() if status == "sent" else None),
        )
        db.add(email)
        db.commit()
        db.refresh(email)
        return _to_dict(email)


def get_all_emails() -> list[dict]:
    with _session() as db:
        rows = db.execute(select(Email).order_by(Email.created_at.desc())).scalars().all()
        return [_to_dict(r) for r in rows]


def get_emails_for_lead(lead_id: str) -> list[dict]:
    with _session() as db:
        rows = db.execute(
            select(Email).where(Email.lead_id == lead_id).order_by(Email.created_at.asc())
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def get_emails_needing_followup(days: int = 3) -> list[dict]:
    """Sent > `days` ago, no reply recorded, no follow-up already queued."""
    cutoff = _now() - timedelta(days=days)
    with _session() as db:
        replied = select(Reply.email_id)
        followed_up = select(FollowUp.original_email_id).where(
            FollowUp.status.in_(["sent", "pending"])
        )
        rows = db.execute(
            select(Email)
            .where(
                Email.status == "sent",
                Email.sent_at.is_not(None),
                Email.sent_at <= cutoff,
                Email.id.not_in(replied),
                Email.id.not_in(followed_up),
            )
            .order_by(Email.sent_at.asc())
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def find_email_by_subject(subject: str, contact_id: str | None = None) -> dict | None:
    """Match an inbound 'Re: ...' back to the sent email (prefix already stripped)."""
    with _session() as db:
        stmt = select(Email).where(
            func.lower(Email.subject) == subject.strip().lower(),
            Email.status.in_(["sent", "replied"]),
        )
        if contact_id:
            stmt = stmt.where(Email.contact_id == contact_id)
        email = db.execute(stmt.order_by(Email.sent_at.desc())).scalars().first()
        return _to_dict(email)


def update_email_status(email_id: str, status: str) -> dict | None:
    with _session() as db:
        email = db.get(Email, email_id)
        if email is None:
            return None
        email.status = status
        if status == "sent" and email.sent_at is None:
            email.sent_at = _now()
        db.commit()
        db.refresh(email)
        return _to_dict(email)


# ── REPLIES ──────────────────────────────────────────────────────────

def create_reply(
    email_id: str,
    raw_body: str,
    received_at: datetime | None = None,
    classification: str | None = None,
    summary: str | None = None,
    next_action: str | None = None,
) -> dict:
    """Record a reply and flip the original email to 'replied'.

    classification/summary/next_action are optional so the classifier can
    either pass them here or update the row afterwards.
    """
    with _session() as db:
        reply = Reply(
            email_id=email_id,
            raw_body=raw_body,
            classification=classification,
            summary=summary,
            next_action=next_action,
            received_at=received_at or _now(),
        )
        db.add(reply)
        email = db.get(Email, email_id)
        if email is not None:
            email.status = "replied"
        db.commit()
        db.refresh(reply)
        return _to_dict(reply)


def update_reply_classification(
    reply_id: str,
    classification: str,
    summary: str | None = None,
    next_action: str | None = None,
) -> dict | None:
    with _session() as db:
        reply = db.get(Reply, reply_id)
        if reply is None:
            return None
        reply.classification = classification
        if summary is not None:
            reply.summary = summary
        if next_action is not None:
            reply.next_action = next_action
        db.commit()
        db.refresh(reply)
        return _to_dict(reply)


def get_all_replies() -> list[dict]:
    with _session() as db:
        rows = db.execute(select(Reply).order_by(Reply.received_at.desc())).scalars().all()
        return [_to_dict(r) for r in rows]


# ── MEETINGS ─────────────────────────────────────────────────────────

def create_meeting(
    lead_id: str,
    contact_id: str | None,
    meeting_link: str | None,
    status: str = "link_sent",
    scheduled_at: datetime | None = None,
    briefing: dict | None = None,
) -> dict:
    with _session() as db:
        meeting = Meeting(
            lead_id=lead_id,
            contact_id=contact_id,
            meeting_link=meeting_link,
            status=status,
            scheduled_at=scheduled_at,
            briefing=briefing,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return _to_dict(meeting)


def get_all_meetings() -> list[dict]:
    with _session() as db:
        rows = db.execute(
            select(Meeting).order_by(
                Meeting.scheduled_at.is_(None), Meeting.scheduled_at.asc()
            )
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def get_upcoming_meetings_needing_reminder(within_minutes: int = 35) -> list[dict]:
    now = _now()
    horizon = now + timedelta(minutes=within_minutes)
    with _session() as db:
        rows = db.execute(
            select(Meeting)
            .where(
                Meeting.admin_notified.is_(False),
                Meeting.scheduled_at.is_not(None),
                Meeting.scheduled_at > now,
                Meeting.scheduled_at <= horizon,
                Meeting.status.in_(["link_sent", "confirmed"]),
            )
            .order_by(Meeting.scheduled_at.asc())
        ).scalars().all()
        return [_to_dict(r) for r in rows]


def update_meeting_admin_notified(meeting_id: str) -> dict | None:
    with _session() as db:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return None
        meeting.admin_notified = True
        db.commit()
        db.refresh(meeting)
        return _to_dict(meeting)


def update_meeting_briefing(meeting_id: str, briefing: dict) -> dict | None:
    with _session() as db:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return None
        meeting.briefing = briefing
        db.commit()
        db.refresh(meeting)
        return _to_dict(meeting)


# ── FOLLOW-UPS ───────────────────────────────────────────────────────

def create_followup(
    lead_id: str,
    email_id: str,
    scheduled_for: datetime | None = None,
    status: str = "sent",
) -> dict:
    """`email_id` is the ORIGINAL email being followed up on."""
    with _session() as db:
        followup = FollowUp(
            lead_id=lead_id,
            original_email_id=email_id,
            scheduled_for=scheduled_for,
            status=status,
        )
        db.add(followup)
        db.commit()
        db.refresh(followup)
        return _to_dict(followup)


def update_followup_sent(followup_id: str, followup_email_id: str) -> dict | None:
    with _session() as db:
        followup = db.get(FollowUp, followup_id)
        if followup is None:
            return None
        followup.followup_email_id = followup_email_id
        followup.status = "sent"
        db.commit()
        db.refresh(followup)
        return _to_dict(followup)
