"""SQLAlchemy models — the single source of truth for the database schema.

Any change here must also be reflected in:
  - .claude/skills/database-schema.md
  - docs/database_schema.md
  - frontend/src/lib/types.ts
and needs an Alembic migration.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base

# ── Enum-ish string constants ────────────────────────────────────────
# Kept as plain strings (not DB enums) so adding a stage during the
# hackathon never needs a migration.

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


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """A prospect company discovered and worked by the pipeline."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(512))
    industry: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    employee_count: Mapped[int | None] = mapped_column(Integer)

    pipeline_stage: Mapped[str] = mapped_column(
        String(64), default="Discovered", nullable=False
    )
    lead_score: Mapped[int | None] = mapped_column(Integer)
    score_explanation: Mapped[str | None] = mapped_column(Text)
    recommended_service: Mapped[str | None] = mapped_column(String(255))
    pitch_angle: Mapped[str | None] = mapped_column(Text)
    icp_fit: Mapped[bool | None] = mapped_column(Boolean)
    research_summary: Mapped[str | None] = mapped_column(Text)
    apollo_data: Mapped[dict | None] = mapped_column(JSON)

    session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    emails: Mapped[list["Email"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    followups: Mapped[list["FollowUp"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list["PipelineEvent"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_leads_session_id", "session_id"),
        Index("ix_leads_pipeline_stage", "pipeline_stage"),
        Index("ix_leads_company_name", "company_name"),
    )


class Contact(Base):
    """A decision maker at a lead company."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="contacts")
    emails: Mapped[list["Email"]] = relationship(back_populates="contact")

    __table_args__ = (
        Index("ix_contacts_lead_id", "lead_id"),
        Index("ix_contacts_email", "email"),
    )


class Email(Base):
    """An outreach email — drafted, sent, failed, or replied to."""

    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    subject: Mapped[str | None] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="emails")
    contact: Mapped["Contact | None"] = relationship(back_populates="emails")
    replies: Mapped[list["Reply"]] = relationship(
        back_populates="email", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_emails_lead_id", "lead_id"),
        Index("ix_emails_status", "status"),
    )


class Reply(Base):
    """An inbound reply to an outreach email, plus its classification."""

    __tablename__ = "replies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    raw_body: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(String(512))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    email: Mapped["Email"] = relationship(back_populates="replies")

    __table_args__ = (Index("ix_replies_email_id", "email_id"),)


class Meeting(Base):
    """A booked (or offered) meeting with a lead's contact."""

    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    meeting_link: Mapped[str | None] = mapped_column(String(512))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    briefing: Mapped[dict | None] = mapped_column(JSON)
    admin_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="link_sent", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="meetings")

    __table_args__ = (
        Index("ix_meetings_lead_id", "lead_id"),
        Index("ix_meetings_scheduled_at", "scheduled_at"),
    )


class FollowUp(Base):
    """A scheduled follow-up on an outreach email that got no reply."""

    __tablename__ = "followups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    original_email_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    followup_email_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="SET NULL")
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="followups")

    __table_args__ = (
        Index("ix_followups_lead_id", "lead_id"),
        Index("ix_followups_original_email_id", "original_email_id"),
    )


class PipelineEvent(Base):
    """An audit trail row — one per stage transition, for the lead timeline."""

    __tablename__ = "pipeline_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[str | None] = mapped_column(String(64))
    to_stage: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="events")

    __table_args__ = (Index("ix_pipeline_events_lead_id", "lead_id"),)
