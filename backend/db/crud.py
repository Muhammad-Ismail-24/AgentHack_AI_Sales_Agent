"""Every database operation in the project. No raw SQL anywhere else.

All functions are async and take an AsyncSession as their first argument.
Routes get one from Depends(get_db); background code uses session_scope().

Synchronous callers (the comms layer's APScheduler jobs) should import
db.sync_crud instead, which mirrors these functions on a sync session.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from utils.validators import clamp_score

log = get_logger(__name__)

# Columns a caller is allowed to set when creating/updating a Lead. Anything
# else in an incoming dict (agent state carries extra keys) is ignored rather
# than blowing up.
_LEAD_FIELDS = {
    "company_name", "website", "industry", "location", "employee_count",
    "pipeline_stage", "lead_score", "score_explanation", "recommended_service",
    "pitch_angle", "icp_fit", "research_summary", "apollo_data", "session_id",
}

_CONTACT_FIELDS = {"name", "role", "email", "linkedin_url", "is_primary"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _filter_lead_fields(data: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in data.items() if k in _LEAD_FIELDS}
    if "lead_score" in clean:
        clean["lead_score"] = clamp_score(clean["lead_score"])
    return clean


# ══════════════════════════════════════════════════════════════════════
# LEADS
# ══════════════════════════════════════════════════════════════════════

async def create_lead(db: AsyncSession, lead_dict: dict[str, Any]) -> Lead:
    """Insert a lead and log its arrival as a PipelineEvent."""
    lead = Lead(**_filter_lead_fields(lead_dict))
    db.add(lead)
    await db.flush()

    db.add(
        PipelineEvent(
            lead_id=lead.id,
            from_stage=None,
            to_stage=lead.pipeline_stage,
            reason="Lead discovered",
        )
    )
    await db.commit()
    await db.refresh(lead)
    log.info("created lead %s (%s)", lead.company_name, lead.id)
    return lead


async def get_lead(db: AsyncSession, lead_id: str) -> Lead | None:
    return await db.get(Lead, lead_id)


async def get_all_leads(db: AsyncSession, session_id: str | None = None) -> list[Lead]:
    """All leads, newest first. Pass session_id to scope to one pipeline run."""
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if session_id:
        stmt = stmt.where(Lead.session_id == session_id)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_lead_by_company(
    db: AsyncSession, company_name: str, session_id: str | None = None
) -> Lead | None:
    """Case-insensitive lookup — used to dedupe leads across pipeline passes."""
    stmt = select(Lead).where(func.lower(Lead.company_name) == company_name.lower())
    if session_id:
        stmt = stmt.where(Lead.session_id == session_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_lead_stage(
    db: AsyncSession, lead_id: str, new_stage: str, reason: str | None = None
) -> Lead | None:
    """Move a lead to a new stage and record the transition on its timeline."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        log.warning("update_lead_stage: lead %s not found", lead_id)
        return None

    old_stage = lead.pipeline_stage
    if old_stage == new_stage:
        return lead

    lead.pipeline_stage = new_stage
    db.add(
        PipelineEvent(
            lead_id=lead.id,
            from_stage=old_stage,
            to_stage=new_stage,
            reason=reason or "Stage updated",
        )
    )
    await db.commit()
    await db.refresh(lead)
    log.info("lead %s: %s -> %s", lead.company_name, old_stage, new_stage)
    return lead


async def update_lead_score(
    db: AsyncSession, lead_id: str, score: int, explanation: str | None = None
) -> Lead | None:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        return None
    lead.lead_score = clamp_score(score)
    if explanation is not None:
        lead.score_explanation = explanation
    await db.commit()
    await db.refresh(lead)
    return lead


async def update_lead_research(
    db: AsyncSession,
    lead_id: str,
    research_summary: str | None = None,
    apollo_data: dict | None = None,
) -> Lead | None:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        return None
    if research_summary is not None:
        lead.research_summary = research_summary
    if apollo_data is not None:
        lead.apollo_data = apollo_data
    await db.commit()
    await db.refresh(lead)
    return lead


async def update_lead_service(
    db: AsyncSession,
    lead_id: str,
    recommended_service: str | None = None,
    pitch_angle: str | None = None,
) -> Lead | None:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        return None
    if recommended_service is not None:
        lead.recommended_service = recommended_service
    if pitch_angle is not None:
        lead.pitch_angle = pitch_angle
    await db.commit()
    await db.refresh(lead)
    return lead


async def update_lead(
    db: AsyncSession, lead_id: str, updates: dict[str, Any]
) -> Lead | None:
    """Generic partial update. Stage changes here still log a PipelineEvent."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        return None

    clean = _filter_lead_fields(updates)
    new_stage = clean.pop("pipeline_stage", None)
    for key, value in clean.items():
        setattr(lead, key, value)

    if new_stage and new_stage != lead.pipeline_stage:
        db.add(
            PipelineEvent(
                lead_id=lead.id,
                from_stage=lead.pipeline_stage,
                to_stage=new_stage,
                reason="Updated manually",
            )
        )
        lead.pipeline_stage = new_stage

    await db.commit()
    await db.refresh(lead)
    return lead


async def upsert_leads_from_pipeline(
    db: AsyncSession, leads_list: list[dict[str, Any]], session_id: str
) -> list[Lead]:
    """Bulk write the pipeline's outreach_queue into the database.

    Matches on company_name within the session: a lead the pipeline has seen
    on an earlier node is updated in place rather than duplicated. Contacts
    supplied under a "contacts" key are upserted by email.
    """
    saved: list[Lead] = []

    for raw in leads_list:
        name = (raw.get("company_name") or "").strip()
        if not name:
            log.warning("skipping lead with no company_name: %s", raw)
            continue

        fields = _filter_lead_fields(raw)
        fields["session_id"] = session_id

        lead = await get_lead_by_company(db, name, session_id)
        if lead is None:
            lead = Lead(**fields)
            db.add(lead)
            await db.flush()
            db.add(
                PipelineEvent(
                    lead_id=lead.id,
                    from_stage=None,
                    to_stage=lead.pipeline_stage,
                    reason="Lead discovered",
                )
            )
        else:
            new_stage = fields.pop("pipeline_stage", None)
            for key, value in fields.items():
                if value is not None:
                    setattr(lead, key, value)
            if new_stage and new_stage != lead.pipeline_stage:
                db.add(
                    PipelineEvent(
                        lead_id=lead.id,
                        from_stage=lead.pipeline_stage,
                        to_stage=new_stage,
                        reason="Advanced by pipeline",
                    )
                )
                lead.pipeline_stage = new_stage

        for contact in raw.get("contacts") or []:
            await _upsert_contact(db, contact, lead.id)

        # Two dicts in one batch can refer to the same company (the pipeline
        # emits a lead again as it advances) — return each lead once.
        if lead not in saved:
            saved.append(lead)

    await db.commit()
    for lead in saved:
        await db.refresh(lead)

    log.info("upserted %s leads for session %s", len(saved), session_id)
    return saved


async def count_leads_by_stage(
    db: AsyncSession, session_id: str | None = None
) -> dict[str, int]:
    """{stage: count} — powers the pipeline status endpoint and Kanban badges."""
    stmt = select(Lead.pipeline_stage, func.count(Lead.id)).group_by(Lead.pipeline_stage)
    if session_id:
        stmt = stmt.where(Lead.session_id == session_id)
    result = await db.execute(stmt)
    return {stage: count for stage, count in result.all()}


# ══════════════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════════════

async def _upsert_contact(
    db: AsyncSession, contact_dict: dict[str, Any], lead_id: str
) -> Contact:
    """Insert or update a contact, matched on email within the lead."""
    fields = {k: v for k, v in contact_dict.items() if k in _CONTACT_FIELDS}
    email = fields.get("email")

    existing = None
    if email:
        result = await db.execute(
            select(Contact).where(Contact.lead_id == lead_id, Contact.email == email)
        )
        existing = result.scalars().first()

    if existing:
        for key, value in fields.items():
            if value is not None:
                setattr(existing, key, value)
        return existing

    contact = Contact(lead_id=lead_id, **fields)
    db.add(contact)
    await db.flush()
    return contact


async def create_contact(
    db: AsyncSession, contact_dict: dict[str, Any], lead_id: str
) -> Contact:
    contact = await _upsert_contact(db, contact_dict, lead_id)
    await db.commit()
    await db.refresh(contact)
    return contact


async def get_contacts_for_lead(db: AsyncSession, lead_id: str) -> list[Contact]:
    """Contacts for a lead, primary contact first."""
    result = await db.execute(
        select(Contact)
        .where(Contact.lead_id == lead_id)
        .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
    )
    return list(result.scalars().all())


async def get_primary_contact(db: AsyncSession, lead_id: str) -> Contact | None:
    """The flagged primary contact, falling back to the first contact found."""
    contacts = await get_contacts_for_lead(db, lead_id)
    return contacts[0] if contacts else None


async def get_contact_by_email(db: AsyncSession, email: str) -> Contact | None:
    """Used by the inbound reply webhook to match a sender to a contact."""
    result = await db.execute(
        select(Contact).where(func.lower(Contact.email) == email.lower())
    )
    return result.scalars().first()


# ══════════════════════════════════════════════════════════════════════
# EMAILS
# ══════════════════════════════════════════════════════════════════════

async def create_email(
    db: AsyncSession,
    lead_id: str,
    contact_id: str | None,
    subject: str,
    body: str,
    status: str = "draft",
    sent_at: datetime | None = None,
) -> Email:
    email = Email(
        lead_id=lead_id,
        contact_id=contact_id,
        subject=subject,
        body=body,
        status=status,
        sent_at=sent_at or (_now() if status == "sent" else None),
    )
    db.add(email)
    await db.commit()
    await db.refresh(email)
    log.info("email %s for lead %s (status=%s)", email.id, lead_id, status)
    return email


async def get_email(db: AsyncSession, email_id: str) -> Email | None:
    return await db.get(Email, email_id)


async def get_all_emails(db: AsyncSession) -> list[Email]:
    result = await db.execute(select(Email).order_by(Email.created_at.desc()))
    return list(result.scalars().unique().all())


async def get_emails_for_lead(db: AsyncSession, lead_id: str) -> list[Email]:
    result = await db.execute(
        select(Email).where(Email.lead_id == lead_id).order_by(Email.created_at.asc())
    )
    return list(result.scalars().unique().all())


async def get_emails_needing_followup(
    db: AsyncSession, days: int = 3
) -> list[Email]:
    """Sent more than `days` ago, never replied to, no follow-up sent yet."""
    cutoff = _now() - timedelta(days=days)

    replied = select(Reply.email_id)
    followed_up = select(FollowUp.original_email_id).where(
        FollowUp.status.in_(["sent", "pending"])
    )

    result = await db.execute(
        select(Email)
        .where(
            Email.status == "sent",
            Email.sent_at.is_not(None),
            Email.sent_at <= cutoff,
            Email.id.not_in(replied),
            Email.id.not_in(followed_up),
        )
        .order_by(Email.sent_at.asc())
    )
    emails = list(result.scalars().unique().all())
    if emails:
        log.info("%s emails are due a follow-up", len(emails))
    return emails


async def find_email_by_subject(
    db: AsyncSession, subject: str, contact_id: str | None = None
) -> Email | None:
    """Match an inbound 'Re: ...' subject back to the email that was sent.

    The webhook strips the Re:/Fwd: prefix before calling this.
    """
    stmt = select(Email).where(
        func.lower(Email.subject) == subject.strip().lower(),
        Email.status.in_(["sent", "replied"]),
    )
    if contact_id:
        stmt = stmt.where(Email.contact_id == contact_id)
    result = await db.execute(stmt.order_by(Email.sent_at.desc()))
    return result.scalars().first()


async def update_email_status(
    db: AsyncSession, email_id: str, status: str
) -> Email | None:
    email = await db.get(Email, email_id)
    if email is None:
        return None
    email.status = status
    if status == "sent" and email.sent_at is None:
        email.sent_at = _now()
    await db.commit()
    await db.refresh(email)
    return email


# ══════════════════════════════════════════════════════════════════════
# REPLIES
# ══════════════════════════════════════════════════════════════════════

async def create_reply(
    db: AsyncSession,
    email_id: str,
    raw_body: str,
    classification: str | None = None,
    summary: str | None = None,
    next_action: str | None = None,
    received_at: datetime | None = None,
) -> Reply:
    """Record an inbound reply and flip the original email to 'replied'."""
    reply = Reply(
        email_id=email_id,
        raw_body=raw_body,
        classification=classification,
        summary=summary,
        next_action=next_action,
        received_at=received_at or _now(),
    )
    db.add(reply)

    email = await db.get(Email, email_id)
    if email is not None:
        email.status = "replied"

    await db.commit()
    await db.refresh(reply)
    log.info("reply on email %s classified as %s", email_id, classification)
    return reply


async def get_all_replies(db: AsyncSession) -> list[Reply]:
    result = await db.execute(select(Reply).order_by(Reply.received_at.desc()))
    return list(result.scalars().unique().all())


async def get_replies_for_lead(db: AsyncSession, lead_id: str) -> list[Reply]:
    result = await db.execute(
        select(Reply)
        .join(Email, Reply.email_id == Email.id)
        .where(Email.lead_id == lead_id)
        .order_by(Reply.received_at.desc())
    )
    return list(result.scalars().unique().all())


# ══════════════════════════════════════════════════════════════════════
# MEETINGS
# ══════════════════════════════════════════════════════════════════════

async def create_meeting(
    db: AsyncSession,
    lead_id: str,
    contact_id: str | None,
    meeting_link: str | None,
    scheduled_at: datetime | None = None,
    status: str = "link_sent",
    briefing: dict | None = None,
) -> Meeting:
    meeting = Meeting(
        lead_id=lead_id,
        contact_id=contact_id,
        meeting_link=meeting_link,
        scheduled_at=scheduled_at,
        status=status,
        briefing=briefing,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    log.info("meeting %s booked for lead %s", meeting.id, lead_id)
    return meeting


async def get_meeting(db: AsyncSession, meeting_id: str) -> Meeting | None:
    return await db.get(Meeting, meeting_id)


async def get_all_meetings(db: AsyncSession) -> list[Meeting]:
    """Meetings ordered by when they happen, soonest first."""
    result = await db.execute(
        select(Meeting).order_by(
            Meeting.scheduled_at.is_(None), Meeting.scheduled_at.asc()
        )
    )
    return list(result.scalars().unique().all())


async def get_meetings_for_lead(db: AsyncSession, lead_id: str) -> list[Meeting]:
    result = await db.execute(
        select(Meeting)
        .where(Meeting.lead_id == lead_id)
        .order_by(Meeting.scheduled_at.asc())
    )
    return list(result.scalars().unique().all())


async def get_upcoming_meetings_needing_reminder(
    db: AsyncSession, within_minutes: int = 35
) -> list[Meeting]:
    """Meetings starting soon that the admin has not been WhatsApped about."""
    now = _now()
    horizon = now + timedelta(minutes=within_minutes)
    result = await db.execute(
        select(Meeting)
        .where(
            Meeting.admin_notified.is_(False),
            Meeting.scheduled_at.is_not(None),
            Meeting.scheduled_at > now,
            Meeting.scheduled_at <= horizon,
            Meeting.status.in_(["link_sent", "confirmed"]),
        )
        .order_by(Meeting.scheduled_at.asc())
    )
    return list(result.scalars().unique().all())


async def update_meeting_admin_notified(
    db: AsyncSession, meeting_id: str
) -> Meeting | None:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        return None
    meeting.admin_notified = True
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def update_meeting_briefing(
    db: AsyncSession, meeting_id: str, briefing_dict: dict
) -> Meeting | None:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        return None
    meeting.briefing = briefing_dict
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def update_meeting_status(
    db: AsyncSession, meeting_id: str, status: str
) -> Meeting | None:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        return None
    meeting.status = status
    await db.commit()
    await db.refresh(meeting)
    return meeting


# ══════════════════════════════════════════════════════════════════════
# FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════════

async def create_followup(
    db: AsyncSession,
    lead_id: str,
    original_email_id: str,
    scheduled_for: datetime | None = None,
    status: str = "pending",
) -> FollowUp:
    followup = FollowUp(
        lead_id=lead_id,
        original_email_id=original_email_id,
        scheduled_for=scheduled_for,
        status=status,
    )
    db.add(followup)
    await db.commit()
    await db.refresh(followup)
    return followup


async def get_pending_followups(db: AsyncSession) -> list[FollowUp]:
    result = await db.execute(
        select(FollowUp)
        .where(FollowUp.status == "pending")
        .order_by(FollowUp.scheduled_for.asc())
    )
    return list(result.scalars().unique().all())


async def update_followup_sent(
    db: AsyncSession, followup_id: str, followup_email_id: str
) -> FollowUp | None:
    followup = await db.get(FollowUp, followup_id)
    if followup is None:
        return None
    followup.followup_email_id = followup_email_id
    followup.status = "sent"
    await db.commit()
    await db.refresh(followup)
    return followup


# ══════════════════════════════════════════════════════════════════════
# PIPELINE EVENTS
# ══════════════════════════════════════════════════════════════════════

async def create_event(
    db: AsyncSession,
    lead_id: str,
    from_stage: str | None,
    to_stage: str | None,
    reason: str | None = None,
) -> PipelineEvent:
    event = PipelineEvent(
        lead_id=lead_id, from_stage=from_stage, to_stage=to_stage, reason=reason
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_events_for_lead(db: AsyncSession, lead_id: str) -> list[PipelineEvent]:
    """Timeline for a lead, oldest first."""
    result = await db.execute(
        select(PipelineEvent)
        .where(PipelineEvent.lead_id == lead_id)
        .order_by(PipelineEvent.created_at.asc())
    )
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ══════════════════════════════════════════════════════════════════════

async def clear_all(db: AsyncSession) -> None:
    """Wipe every table. Dev only — used by load_seeds.py before seeding."""
    for model in (PipelineEvent, FollowUp, Meeting, Reply, Email, Contact, Lead):
        await db.execute(model.__table__.delete())
    await db.commit()
    log.warning("cleared all tables")
