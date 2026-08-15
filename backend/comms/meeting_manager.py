"""
Handles meeting requests: generates a booking link, records the meeting,
confirms it to the prospect by email, notifies the admin on WhatsApp, and
(separately, via send_pre_meeting_reminder) sends a pre-meeting briefing
shortly before the scheduled time.

Two dependencies aren't built yet in this branch and are borrowed the same
way backend/config, backend/utils, and backend/db are borrowed elsewhere
in comms/ (see comms/_deps.py and conflicts.md):

  - tools.calendar_tool.generate_booking_link — owned by Ismail
    (backend/tools/, per FOLDER_STRUCTURE.md). Falls back to a
    deterministic fake cal.com-style link when absent.
  - comms.whatsapp_notifier.WhatsAppNotifier — Sufiyan's own Step 6, just
    not built yet in this session ("stick to numerical order"). Falls
    back to a stub that logs and reports whatsapp_sent=False.

Both fall-backs disappear automatically once the real modules exist —
nothing in this file needs to change.
"""

import re

from comms._deps import crud, get_logger
from comms._llm import complete_json
from comms.email_sender import EmailSender
from config.prompts import MEETING_BRIEFING_PROMPT

_log = get_logger("comms.meeting_manager")

try:
    from tools.calendar_tool import generate_booking_link  # type: ignore

    _USING_REAL_CALENDAR_TOOL = True
except ImportError:
    _USING_REAL_CALENDAR_TOOL = False

    def generate_booking_link(company_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-") or "meeting"
        return f"https://cal.com/admin/{slug}"

    _log.warning(
        "tools.calendar_tool not found (Ismail's backend/tools/, not yet built) - "
        "meeting_manager using a mock booking link generator"
    )

try:
    from comms.whatsapp_notifier import WhatsAppNotifier  # type: ignore

    _USING_REAL_WHATSAPP_NOTIFIER = True
except ImportError:
    _USING_REAL_WHATSAPP_NOTIFIER = False

    class WhatsAppNotifier:  # Step 6 stub — not built yet this session
        async def send_meeting_confirmed(self, **kwargs) -> bool:
            _log.warning("whatsapp_notifier.py not built yet (Step 6) - skipping meeting-confirmed WhatsApp message")
            return False

        async def send_pre_meeting_briefing(self, **kwargs) -> bool:
            _log.warning("whatsapp_notifier.py not built yet (Step 6) - skipping pre-meeting WhatsApp briefing")
            return False

    _log.info("comms.whatsapp_notifier not found - MeetingManager using a stub notifier for now")


def _mock_briefing(lead: dict) -> dict:
    return {
        "customer_problem": lead.get("research_summary", "(no research summary on file)"),
        "recommended_service": lead.get("recommended_service", "(no recommendation on file)"),
        "key_points": ["(mock) Confirm current pain points", "(mock) Walk through the recommended service"],
        "watch_out_for": ["(mock) Budget sign-off", "(mock) Integration timeline"],
    }


class MeetingManager:
    def __init__(self) -> None:
        self._email_sender = EmailSender()
        self._whatsapp = WhatsAppNotifier()

    async def handle_meeting_request(self, lead_id: str) -> dict:
        lead = crud.get_lead(lead_id)
        contact = crud.get_primary_contact(lead_id)
        if lead is None or contact is None:
            _log.error("handle_meeting_request: lead or contact not found for lead_id=%s", lead_id)
            return {"meeting_link": None, "email_sent": False, "whatsapp_sent": False}

        company_name = lead["company_name"]
        meeting_link = generate_booking_link(company_name)

        crud.create_meeting(
            lead_id=lead_id,
            contact_id=contact["id"],
            meeting_link=meeting_link,
            status="link_sent",
        )

        email_result = await self._email_sender.send(
            to_email=contact["email"],
            subject=f"Meeting Link - {company_name}",
            body=(
                f"Hi {contact['name']},\n\n"
                f"Here's a link to book a time that works for you: {meeting_link}\n\n"
                f"Looking forward to it!"
            ),
            lead_id=lead_id,
            contact_id=contact["id"],
        )

        whatsapp_sent = await self._whatsapp.send_meeting_confirmed(
            company_name=company_name,
            contact_name=contact["name"],
            contact_role=contact.get("role", ""),
            meeting_link=meeting_link,
            scheduled_time="pending prospect selection",
        )

        crud.update_lead_stage(lead_id, "Meeting Scheduled")

        return {
            "meeting_link": meeting_link,
            "email_sent": bool(email_result.get("success")),
            "whatsapp_sent": bool(whatsapp_sent),
        }

    async def send_pre_meeting_reminder(self, meeting_id: str) -> None:
        meeting = crud.get_meeting(meeting_id)
        if meeting is None:
            _log.error("send_pre_meeting_reminder: meeting_id=%s not found", meeting_id)
            return

        lead = crud.get_lead(meeting["lead_id"])
        if lead is None:
            _log.error("send_pre_meeting_reminder: lead not found for meeting_id=%s", meeting_id)
            return

        company_name = lead["company_name"]
        thread_emails = [e for e in crud.get_all_emails() if e["lead_id"] == meeting["lead_id"]]
        email_thread_summary = (
            "\n".join(f"- {e['subject']}: {e['body'][:200]}" for e in thread_emails)
            or "(no prior emails on record)"
        )

        user = MEETING_BRIEFING_PROMPT["user_template"].format(
            company_name=company_name,
            research_summary=lead.get("research_summary", ""),
            recommended_service=lead.get("recommended_service", ""),
            email_thread_summary=email_thread_summary,
        )
        briefing = await complete_json(
            system=MEETING_BRIEFING_PROMPT["system"],
            user=user,
            max_tokens=768,
            mock_fallback=lambda: _mock_briefing(lead),
        )
        if not briefing:
            briefing = _mock_briefing(lead)

        await self._whatsapp.send_pre_meeting_briefing(company_name=company_name, briefing=briefing)
        crud.mark_meeting_admin_notified(meeting_id)
        _log.info("Pre-meeting reminder sent for %s", company_name)
