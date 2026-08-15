"""
APScheduler-driven follow-up email job. Wakes up on an interval, finds
outreach emails that received no reply after 3 days, writes a short
follow-up via Claude, and sends it.

NOT wired into backend/main.py yet — main.py belongs to Wajeeh and does not
exist in this branch. start_scheduler() is written and ready; registering
it via a FastAPI startup hook is tracked as a merge task in conflicts.md.
"""

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from comms._deps import crud, get_logger
from comms._llm import complete_json
from comms.email_sender import EmailSender
from config.prompts import FOLLOWUP_EMAIL_PROMPT

_log = get_logger("comms.followup_scheduler")

scheduler = AsyncIOScheduler()
_email_sender = EmailSender()

FOLLOWUP_AFTER_DAYS = 3
FOLLOWUP_CHECK_INTERVAL_HOURS = 6


def _mock_followup_email(company_name: str, original_subject: str) -> dict:
    return {
        "subject": f"Re: {original_subject}",
        "body": (
            f"Hi — just floating this back up in case the timing was off "
            f"last time. Happy to answer any questions whenever works for "
            f"{company_name}. No pressure either way!"
        ),
    }


async def check_and_send_followups() -> int:
    """
    Query for emails needing a follow-up, generate + send one for each.
    Returns the count of follow-ups sent (also used by test_comms.py to
    report how many would qualify right now).
    """
    candidates = crud.get_emails_needing_followup(days=FOLLOWUP_AFTER_DAYS)
    sent_count = 0

    for email in candidates:
        lead = crud.get_lead(email["lead_id"])
        contact = crud.get_primary_contact(email["lead_id"])
        if lead is None or contact is None:
            _log.warning("Skipping follow-up for email_id=%s - lead or contact not found", email["id"])
            continue

        company_name = lead["company_name"]
        user = FOLLOWUP_EMAIL_PROMPT["user_template"].format(
            original_subject=email["subject"],
            original_body_summary=email["body"][:200],
            contact_name=contact["name"],
            company_name=company_name,
            recommended_service=lead.get("recommended_service", "our service"),
        )
        draft = await complete_json(
            system=FOLLOWUP_EMAIL_PROMPT["system"],
            user=user,
            max_tokens=512,
            mock_fallback=lambda: _mock_followup_email(company_name, email["subject"]),
        )
        if not draft.get("subject") or not draft.get("body"):
            _log.error("Follow-up draft missing subject/body for email_id=%s - skipping", email["id"])
            continue

        result = await _email_sender.send(
            to_email=contact["email"],
            subject=draft["subject"],
            body=draft["body"],
            lead_id=email["lead_id"],
            contact_id=contact["id"],
        )
        if result.get("success"):
            crud.create_followup(
                lead_id=email["lead_id"],
                email_id=email["id"],
                scheduled_for=datetime.now(timezone.utc),
                status="sent",
            )
            _log.info("Follow-up sent to %s", company_name)
            sent_count += 1

    return sent_count


async def schedule_followup(lead_id: str, days: int = 14) -> dict:
    """
    Schedule a follow-up N days out for a lead — used by
    response_classifier.decide_next_action() for the "Not Now" branch.
    """
    scheduled_for = datetime.now(timezone.utc) + timedelta(days=days)
    return crud.create_followup(lead_id=lead_id, email_id="", scheduled_for=scheduled_for, status="scheduled")


def start_scheduler() -> None:
    scheduler.add_job(
        check_and_send_followups,
        "interval",
        hours=FOLLOWUP_CHECK_INTERVAL_HOURS,
        id="check_and_send_followups",
        replace_existing=True,
    )
    scheduler.start()
    _log.info("Follow-up scheduler started - checking every %sh", FOLLOWUP_CHECK_INTERVAL_HOURS)
