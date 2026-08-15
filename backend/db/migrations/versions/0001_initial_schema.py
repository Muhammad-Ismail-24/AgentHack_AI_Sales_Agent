"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("website", sa.String(512)),
        sa.Column("industry", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("employee_count", sa.Integer),
        sa.Column("pipeline_stage", sa.String(64), nullable=False, server_default="Discovered"),
        sa.Column("lead_score", sa.Integer),
        sa.Column("score_explanation", sa.Text),
        sa.Column("recommended_service", sa.String(255)),
        sa.Column("pitch_angle", sa.Text),
        sa.Column("icp_fit", sa.Boolean),
        sa.Column("research_summary", sa.Text),
        sa.Column("apollo_data", sa.JSON),
        sa.Column("session_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_leads_session_id", "leads", ["session_id"])
    op.create_index("ix_leads_pipeline_stage", "leads", ["pipeline_stage"])
    op.create_index("ix_leads_company_name", "leads", ["company_name"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(36),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255)),
        sa.Column("role", sa.String(255)),
        sa.Column("email", sa.String(320)),
        sa.Column("linkedin_url", sa.String(512)),
        sa.Column("is_primary", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_contacts_lead_id", "contacts", ["lead_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    op.create_table(
        "emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(36),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.String(36),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("subject", sa.String(512)),
        sa.Column("body", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_emails_lead_id", "emails", ["lead_id"])
    op.create_index("ix_emails_status", "emails", ["status"])

    op.create_table(
        "replies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "email_id",
            sa.String(36),
            sa.ForeignKey("emails.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_body", sa.Text),
        sa.Column("classification", sa.String(64)),
        sa.Column("summary", sa.Text),
        sa.Column("next_action", sa.String(512)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_replies_email_id", "replies", ["email_id"])

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(36),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.String(36),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("meeting_link", sa.String(512)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("briefing", sa.JSON),
        sa.Column("admin_notified", sa.Boolean, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="link_sent"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_meetings_lead_id", "meetings", ["lead_id"])
    op.create_index("ix_meetings_scheduled_at", "meetings", ["scheduled_at"])

    op.create_table(
        "followups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(36),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "original_email_id",
            sa.String(36),
            sa.ForeignKey("emails.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "followup_email_id",
            sa.String(36),
            sa.ForeignKey("emails.id", ondelete="SET NULL"),
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_followups_lead_id", "followups", ["lead_id"])
    op.create_index("ix_followups_original_email_id", "followups", ["original_email_id"])

    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(36),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", sa.String(64)),
        sa.Column("to_stage", sa.String(64)),
        sa.Column("reason", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_pipeline_events_lead_id", "pipeline_events", ["lead_id"])


def downgrade() -> None:
    op.drop_table("pipeline_events")
    op.drop_table("followups")
    op.drop_table("meetings")
    op.drop_table("replies")
    op.drop_table("emails")
    op.drop_table("contacts")
    op.drop_table("leads")
