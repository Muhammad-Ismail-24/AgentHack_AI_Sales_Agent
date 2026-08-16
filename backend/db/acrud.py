"""Async wrappers around db/crud.py, for FastAPI route handlers.

The Firestore Admin SDK is synchronous and does real network I/O, so calling
it straight from an `async def` handler would block the event loop for the
duration of every query. Each wrapper here hands the call to a worker thread
instead.

Signatures mirror `db/crud.py` exactly — only `await` is added:

    from db import acrud
    leads = await acrud.get_all_leads(session_id)
"""

import asyncio
from datetime import datetime
from typing import Any

from db import crud


async def _run(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


# ── Leads ────────────────────────────────────────────────────────────

async def create_lead(lead_dict: dict[str, Any]) -> dict:
    return await _run(crud.create_lead, lead_dict)


async def get_lead(lead_id: str) -> dict | None:
    return await _run(crud.get_lead, lead_id)


async def get_all_leads(session_id: str | None = None) -> list[dict]:
    return await _run(crud.get_all_leads, session_id)


async def get_lead_by_company(
    company_name: str, session_id: str | None = None
) -> dict | None:
    return await _run(crud.get_lead_by_company, company_name, session_id)


async def update_lead(lead_id: str, updates: dict[str, Any]) -> dict | None:
    return await _run(crud.update_lead, lead_id, updates)


async def update_lead_stage(
    lead_id: str, stage: str, reason: str | None = None
) -> dict | None:
    return await _run(crud.update_lead_stage, lead_id, stage, reason)


async def update_lead_score(
    lead_id: str, score: int, explanation: str | None = None
) -> dict | None:
    return await _run(crud.update_lead_score, lead_id, score, explanation)


async def update_lead_research(
    lead_id: str,
    research_summary: str | None = None,
    apollo_data: dict | None = None,
) -> dict | None:
    return await _run(crud.update_lead_research, lead_id, research_summary, apollo_data)


async def update_lead_service(
    lead_id: str,
    recommended_service: str | None = None,
    pitch_angle: str | None = None,
) -> dict | None:
    return await _run(crud.update_lead_service, lead_id, recommended_service, pitch_angle)


async def delete_lead(lead_id: str) -> bool:
    return await _run(crud.delete_lead, lead_id)


async def upsert_leads_from_pipeline(
    leads_list: list[dict[str, Any]], session_id: str
) -> list[dict]:
    return await _run(crud.upsert_leads_from_pipeline, leads_list, session_id)


async def count_leads_by_stage(session_id: str | None = None) -> dict[str, int]:
    return await _run(crud.count_leads_by_stage, session_id)


# ── Contacts ─────────────────────────────────────────────────────────

async def create_contact(contact_dict: dict[str, Any], lead_id: str) -> dict:
    return await _run(crud.create_contact, contact_dict, lead_id)


async def get_contact(contact_id: str) -> dict | None:
    return await _run(crud.get_contact, contact_id)


async def get_contacts_for_lead(lead_id: str) -> list[dict]:
    return await _run(crud.get_contacts_for_lead, lead_id)


async def get_primary_contact(lead_id: str) -> dict | None:
    return await _run(crud.get_primary_contact, lead_id)


async def get_contact_by_email(email: str) -> dict | None:
    return await _run(crud.get_contact_by_email, email)


# ── Emails ───────────────────────────────────────────────────────────

async def create_email(
    lead_id: str,
    contact_id: str | None,
    subject: str,
    body: str,
    status: str = "draft",
    sent_at: datetime | None = None,
) -> dict:
    return await _run(
        crud.create_email, lead_id, contact_id, subject, body, status, sent_at
    )


async def get_email(email_id: str) -> dict | None:
    return await _run(crud.get_email, email_id)


async def get_all_emails() -> list[dict]:
    return await _run(crud.get_all_emails)


async def get_emails_for_lead(lead_id: str) -> list[dict]:
    return await _run(crud.get_emails_for_lead, lead_id)


async def get_emails_needing_followup(days: int = 3) -> list[dict]:
    return await _run(crud.get_emails_needing_followup, days)


async def find_email_by_subject(
    subject: str, contact_id: str | None = None
) -> dict | None:
    return await _run(crud.find_email_by_subject, subject, contact_id)


async def update_email_status(email_id: str, status: str) -> dict | None:
    return await _run(crud.update_email_status, email_id, status)


# ── Replies ──────────────────────────────────────────────────────────

async def create_reply(
    email_id: str,
    raw_body: str,
    received_at: datetime | None = None,
    classification: str | None = None,
    summary: str | None = None,
    next_action: str | None = None,
) -> dict:
    return await _run(
        crud.create_reply,
        email_id,
        raw_body,
        received_at,
        classification,
        summary,
        next_action,
    )


async def get_all_replies() -> list[dict]:
    return await _run(crud.get_all_replies)


async def get_replies_for_lead(lead_id: str) -> list[dict]:
    return await _run(crud.get_replies_for_lead, lead_id)


# ── Meetings ─────────────────────────────────────────────────────────

async def create_meeting(
    lead_id: str,
    contact_id: str | None,
    meeting_link: str | None,
    status: str = "link_sent",
    scheduled_at: datetime | None = None,
    briefing: dict | None = None,
) -> dict:
    return await _run(
        crud.create_meeting, lead_id, contact_id, meeting_link, status, scheduled_at, briefing
    )


async def get_meeting(meeting_id: str) -> dict | None:
    return await _run(crud.get_meeting, meeting_id)


async def get_all_meetings() -> list[dict]:
    return await _run(crud.get_all_meetings)


async def get_meetings_for_lead(lead_id: str) -> list[dict]:
    return await _run(crud.get_meetings_for_lead, lead_id)


async def get_meetings_needing_reminder(window_minutes: int = 35) -> list[dict]:
    return await _run(crud.get_meetings_needing_reminder, window_minutes)


async def mark_meeting_admin_notified(meeting_id: str) -> dict | None:
    return await _run(crud.mark_meeting_admin_notified, meeting_id)


async def update_meeting_briefing(meeting_id: str, briefing: dict) -> dict | None:
    return await _run(crud.update_meeting_briefing, meeting_id, briefing)


async def update_meeting_status(meeting_id: str, status: str) -> dict | None:
    return await _run(crud.update_meeting_status, meeting_id, status)


# ── Follow-ups ───────────────────────────────────────────────────────

async def create_followup(
    lead_id: str,
    email_id: str,
    scheduled_for: datetime | None = None,
    status: str = "pending",
) -> dict:
    return await _run(crud.create_followup, lead_id, email_id, scheduled_for, status)


async def get_pending_followups() -> list[dict]:
    return await _run(crud.get_pending_followups)


async def update_followup_sent(followup_id: str, followup_email_id: str) -> dict | None:
    return await _run(crud.update_followup_sent, followup_id, followup_email_id)


# ── Pipeline events ──────────────────────────────────────────────────

async def create_event(
    lead_id: str,
    from_stage: str | None,
    to_stage: str | None,
    reason: str | None = None,
) -> dict:
    return await _run(crud.create_event, lead_id, from_stage, to_stage, reason)


async def get_events_for_lead(lead_id: str) -> list[dict]:
    return await _run(crud.get_events_for_lead, lead_id)


# ── Devil's Advocate verdicts ────────────────────────────────────────

async def create_verdict(lead_id: str, debate: dict[str, Any]) -> dict:
    return await _run(crud.create_verdict, lead_id, debate)


async def get_latest_verdict(lead_id: str) -> dict | None:
    return await _run(crud.get_latest_verdict, lead_id)


# ── Deal autopsies ───────────────────────────────────────────────────

async def create_autopsy(lead_id: str, findings: dict[str, Any]) -> dict:
    return await _run(crud.create_autopsy, lead_id, findings)


async def get_latest_autopsy(lead_id: str) -> dict | None:
    return await _run(crud.get_latest_autopsy, lead_id)


async def get_all_autopsies() -> list[dict]:
    return await _run(crud.get_all_autopsies)


# ── Maintenance ──────────────────────────────────────────────────────

async def clear_all() -> None:
    return await _run(crud.clear_all)
