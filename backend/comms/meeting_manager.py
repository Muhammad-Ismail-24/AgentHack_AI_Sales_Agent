"""
Handles meeting requests: generates a booking link, records the meeting,
confirms it to the prospect by email, notifies the admin on WhatsApp, messages
the company directly on WhatsApp when their contact has a phone on file
(extra credit — see whatsapp_notifier.py), and (separately, via
send_pre_meeting_reminder) sends the admin a pre-meeting briefing shortly
before the scheduled time.

comms.whatsapp_notifier.WhatsAppNotifier is real as of the Green API
integration — the try/except below and its stub fallback are dead code in
this merged repo (tools.calendar_tool, Ismail's, may still be pending; see
merge_notes.md), kept only as a defensive guard rather than an assumed gap.
"""

import re

from comms._deps import crud, get_logger
from comms._llm import complete_json_groq
from comms.email_sender import EmailSender
from config.prompts import MEETING_BRIEFING_PROMPT
from tools import tts_generator

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

        async def send_company_meeting_confirmation(self, **kwargs) -> bool:
            _log.warning("whatsapp_notifier.py not built yet (Step 6) - skipping company-facing WhatsApp message")
            return False

        async def send_audio_briefing(self, **kwargs) -> bool:
            _log.warning("whatsapp_notifier.py not built yet (Step 6) - skipping drive-time audio briefing")
            return False

    _log.info("comms.whatsapp_notifier not found - MeetingManager using a stub notifier for now")


def _mock_briefing(lead: dict) -> dict:
    company = lead.get("company_name") or "your prospect"
    return {
        "customer_problem": lead.get("research_summary", "(no research summary on file)"),
        "recommended_service": lead.get("recommended_service", "(no recommendation on file)"),
        "evidence": "low evidence",
        "opening_line": f"(mock) Thanks for making the time — I wanted to pick up where the thread with {company} left off.",
        "key_points": ["(mock) Confirm current pain points", "(mock) Walk through the recommended service"],
        "objections": [
            {"objection": "(mock) We already have something for this.", "rebuttal": "(mock) Ask what it does not cover today."},
            {"objection": "(mock) This is not budgeted.", "rebuttal": "(mock) Offer the smallest scoped starting point."},
        ],
        "watch_out_for": ["(mock) Budget sign-off", "(mock) Integration timeline"],
    }


def _normalise_objections(raw: object) -> list[dict]:
    """Coerce whatever the model returned into [{objection, rebuttal}, ...].

    The schema asks for pairs, but a bare list of strings comes back often
    enough that dropping them would leave the whisper's best section empty.
    """
    if not isinstance(raw, list):
        return []

    pairs: list[dict] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("objection"):
            pairs.append(
                {
                    "objection": str(entry["objection"]),
                    "rebuttal": str(entry.get("rebuttal") or "(no rebuttal drafted)"),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            pairs.append({"objection": entry, "rebuttal": "(no rebuttal drafted)"})
    return pairs


class MeetingManager:
    def __init__(self) -> None:
        self._email_sender = EmailSender()
        self._whatsapp = WhatsAppNotifier()

    async def handle_meeting_request(self, lead_id: str) -> dict:
        lead = crud.get_lead(lead_id)
        contact = crud.get_primary_contact(lead_id)
        if lead is None or contact is None:
            _log.error("handle_meeting_request: lead or contact not found for lead_id=%s", lead_id)
            return {
                "meeting_link": None,
                "email_sent": False,
                "whatsapp_sent": False,
                "company_whatsapp_sent": False,
            }

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

        # Extra credit: message the company directly on WhatsApp when their
        # contact record has a phone number on file. Skipped entirely (no
        # network call attempted) rather than sent-and-failed when absent —
        # most contacts won't have one yet, since decision_maker_agent.py
        # doesn't currently populate `phone`.
        company_whatsapp_sent = False
        contact_phone = contact.get("phone")
        if contact_phone:
            company_whatsapp_sent = await self._whatsapp.send_company_meeting_confirmation(
                to_number=contact_phone,
                company_name=company_name,
                contact_name=contact["name"],
                meeting_link=meeting_link,
                scheduled_time="pending prospect selection",
            )

        crud.update_lead_stage(lead_id, "Meeting Scheduled")

        return {
            "meeting_link": meeting_link,
            "email_sent": bool(email_result.get("success")),
            "whatsapp_sent": bool(whatsapp_sent),
            "company_whatsapp_sent": company_whatsapp_sent,
        }

    async def build_whisper(self, meeting_id: str) -> dict | None:
        """Write the pre-call script for a meeting and store it on the record.

        This is the Executive Whisperer: not a summary of the deal but the
        actual sentences to say — a verbatim opening line, the two objections
        the prospect will raise with the rebuttal for each, and the evidence
        the problem statement rests on. The older briefing keys
        (customer_problem, recommended_service, key_points, watch_out_for)
        are still produced, so anything already reading a briefing keeps
        working unchanged.

        Runs on Groq. Needs GROQ_API_KEY; without it the mock briefing is
        stored and the T-30min reminder still fires with it.

        Returns None only when the meeting or its lead is missing.
        """
        meeting = crud.get_meeting(meeting_id)
        if meeting is None:
            _log.error("build_whisper: meeting_id=%s not found", meeting_id)
            return None

        lead = crud.get_lead(meeting["lead_id"])
        if lead is None:
            _log.error("build_whisper: lead not found for meeting_id=%s", meeting_id)
            return None

        contact = (
            crud.get_contact(meeting.get("contact_id"))
            if meeting.get("contact_id")
            else crud.get_primary_contact(meeting["lead_id"])
        ) or {}

        thread_emails = crud.get_emails_for_lead(meeting["lead_id"])
        email_thread_summary = (
            "\n".join(
                f"- {e.get('subject') or '(no subject)'}: {(e.get('body') or '')[:200]}"
                for e in thread_emails
            )
            or "(no prior emails on record)"
        )

        replies = crud.get_replies_for_lead(meeting["lead_id"])
        reply_summary = (
            "\n".join(
                f"- [{r.get('classification') or 'unclassified'}] "
                f"{r.get('summary') or (r.get('raw_body') or '')[:200]}"
                for r in replies
            )
            or "(they have not replied yet)"
        )

        user = MEETING_BRIEFING_PROMPT["user_template"].format(
            company_name=lead["company_name"],
            contact_name=contact.get("name") or "the attendee",
            contact_role=contact.get("role") or "unknown role",
            research_summary=lead.get("research_summary", ""),
            recommended_service=lead.get("recommended_service", ""),
            pitch_angle=lead.get("pitch_angle", ""),
            email_thread_summary=email_thread_summary,
            reply_summary=reply_summary,
        )
        # Groq, not Gemini — the Whisperer is part of the extra-credit layer.
        # The rest of this module (meeting confirmation email, WhatsApp) makes
        # no LLM call at all, and the reply classifier and follow-up writer in
        # their own modules still go through complete_json() on Gemini.
        whisper = await complete_json_groq(
            system=MEETING_BRIEFING_PROMPT["system"],
            user=user,
            max_tokens=1024,
            mock_fallback=lambda: _mock_briefing(lead),
        )
        if not whisper:
            whisper = _mock_briefing(lead)

        whisper["objections"] = _normalise_objections(whisper.get("objections"))
        crud.update_meeting_briefing(meeting_id, whisper)
        return whisper

    async def deliver_audio_briefing(self, meeting_id: str) -> dict:
        """Render the whisper as a voice note and send it to the admin.

        Audio is a bonus layer over the text script, so every failure here is
        soft: no TTS key, a provider error, or a WhatsApp send that does not
        land all return `audio_url: None` with the whisper still intact.
        """
        meeting = crud.get_meeting(meeting_id)
        whisper = (meeting or {}).get("briefing") or await self.build_whisper(meeting_id)
        if not whisper:
            return {"whisper": None, "audio_url": None, "whatsapp_sent": False}

        lead = crud.get_lead(meeting["lead_id"]) if meeting else None
        company_name = (lead or {}).get("company_name") or "the prospect"

        script = tts_generator.script_from_whisper(whisper, company_name)
        path = await tts_generator.synthesize(script, f"whisper-{meeting_id}")
        if path is None:
            return {"whisper": whisper, "audio_url": None, "whatsapp_sent": False}

        whatsapp_sent = await self._whatsapp.send_audio_briefing(
            company_name=company_name, audio_path=str(path)
        )
        return {
            "whisper": whisper,
            "audio_url": f"/audio/{path.name}",
            "script": script,
            "whatsapp_sent": bool(whatsapp_sent),
        }

    async def send_pre_meeting_reminder(self, meeting_id: str) -> None:
        """T-30min: WhatsApp the admin the pre-call script, then the voice note.

        Called by the APScheduler job in followup_scheduler.py.
        """
        whisper = await self.build_whisper(meeting_id)
        if whisper is None:
            return

        meeting = crud.get_meeting(meeting_id)
        lead = crud.get_lead(meeting["lead_id"]) if meeting else None
        company_name = (lead or {}).get("company_name") or "the prospect"

        await self._whatsapp.send_pre_meeting_briefing(
            company_name=company_name,
            briefing=whisper,
            meeting_link=(meeting or {}).get("meeting_link"),
        )
        # Best-effort: the text script has already landed, so a failed voice
        # note costs the admin nothing.
        await self.deliver_audio_briefing(meeting_id)

        crud.mark_meeting_admin_notified(meeting_id)
        _log.info("Pre-meeting whisper sent for %s", company_name)
