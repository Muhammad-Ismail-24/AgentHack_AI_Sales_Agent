"""
Sends WhatsApp notifications for the meeting-scheduling flow:

  - Admin-facing: a meeting-confirmed alert (from
    meeting_manager.handle_meeting_request) and a 30-minute pre-meeting
    briefing (from meeting_manager.send_pre_meeting_reminder).
  - Company-facing (extra credit): a short meeting-confirmation message
    sent directly to the prospect's own WhatsApp, when their contact
    record has a phone number on file. Deliberately does not include the
    internal briefing (objections, watch-outs) — that's admin-only.

Two transports, tried in order at construction time:

  1. Green API (settings.GREEN_API_ID_INSTANCE / GREEN_API_TOKEN_INSTANCE)
     — plain REST, no SDK: POST {apiUrl}/waInstance{id}/sendMessage/{token}
     with {"chatId": "<digits>@c.us", "message": "..."}. The active path.
  2. Twilio (settings.TWILIO_ACCOUNT_SID / ...) — legacy fallback, kept for
     anyone who already has Twilio WhatsApp sandbox access configured.
  3. Mock — logs the payload and returns True, so the demo and comms tests
     run with no credentials at all. (Only the mock path is unconditionally
     "successful" — the two real transports correctly report failure when
     no recipient number is available, rather than pretending to send.)

Message templates match sufiyan_work.md's Step 6 spec verbatim, emoji
included. See utils/logger.py's _make_console_utf8_safe() for the UTF-8
console fix that keeps that content from mangling — or raising — in
mock-mode log output on Windows.
"""

import re
from pathlib import Path

import httpx

from comms._deps import get_logger, settings

_log = get_logger("comms.whatsapp_notifier")


def _to_chat_id(phone: str) -> str:
    """Green API addresses a chat as '<digits>@c.us'. Strip everything but
    digits so callers can pass loosely formatted numbers
    ("+971 50 123 4567", "971-50-123-4567", "971501234567", ...)."""
    digits = re.sub(r"\D", "", phone or "")
    return f"{digits}@c.us"


class WhatsAppNotifier:
    def __init__(self) -> None:
        self.green_api_url = (settings.GREEN_API_URL or "").rstrip("/")
        self.id_instance = settings.GREEN_API_ID_INSTANCE
        self.token_instance = settings.GREEN_API_TOKEN_INSTANCE
        self.admin_number = settings.ADMIN_WHATSAPP_NUMBER

        self.transport = "mock"
        self._twilio_client = None

        if self.green_api_url and self.id_instance and self.token_instance:
            self.transport = "green_api"
            _log.info(
                "WhatsAppNotifier using Green API (instance %s)", self.id_instance
            )
        else:
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            from_number = settings.TWILIO_WHATSAPP_FROM
            if all((account_sid, auth_token, from_number, self.admin_number)):
                try:
                    from twilio.rest import Client

                    self._twilio_client = Client(account_sid, auth_token)
                    self._twilio_from = from_number
                    self.transport = "twilio"
                    _log.info("WhatsAppNotifier using Twilio (legacy fallback)")
                except ImportError:
                    _log.warning("twilio package not installed - falling back to MOCK MODE")

        if self.transport == "mock":
            _log.warning(
                "No WhatsApp credentials configured (Green API or Twilio) - "
                "WhatsAppNotifier running in MOCK MODE"
            )

    @property
    def mock(self) -> bool:
        """Kept as a property so existing callers and tests still read it."""
        return self.transport == "mock"

    async def _send_green_api(self, to_number: str, message: str) -> bool:
        url = f"{self.green_api_url}/waInstance{self.id_instance}/sendMessage/{self.token_instance}"
        payload = {"chatId": _to_chat_id(to_number), "message": message}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            _log.info("WhatsApp message sent via Green API to %s", to_number)
            return True
        except Exception as exc:  # noqa: BLE001 — comms layer must not crash the pipeline
            _log.error("Green API send to %s failed: %s", to_number, exc)
            return False

    async def _send_twilio(self, to_number: str, message: str) -> bool:
        import asyncio

        try:
            # twilio's SDK is synchronous — run it off the event loop so it
            # doesn't block the scheduler jobs sharing this loop.
            await asyncio.to_thread(
                self._twilio_client.messages.create,
                from_=f"whatsapp:{self._twilio_from}",
                to=f"whatsapp:{to_number}",
                body=message,
            )
            _log.info("WhatsApp message sent via Twilio to %s", to_number)
            return True
        except Exception as exc:  # noqa: BLE001
            _log.error("Twilio send to %s failed: %s", to_number, exc)
            return False

    async def _send(self, to_number: str, message: str) -> bool:
        if self.transport == "green_api":
            if not to_number:
                _log.warning("Green API send skipped - no recipient number provided")
                return False
            return await self._send_green_api(to_number, message)

        if self.transport == "twilio":
            if not to_number:
                _log.warning("Twilio send skipped - no recipient number provided")
                return False
            return await self._send_twilio(to_number, message)

        # Mock mode stays unconditionally "successful" (even with no number
        # configured) — it's an explicit simulation, not a real send, and
        # existing demos/tests rely on that to run with zero credentials.
        _log.info(
            "MOCK WhatsApp send to %s:\n%s",
            to_number or "(no recipient number configured)",
            message,
        )
        return True

    # -- admin-facing -------------------------------------------------------
    async def send_meeting_confirmed(
        self,
        company_name: str,
        contact_name: str,
        contact_role: str,
        meeting_link: str,
        scheduled_time: str,
    ) -> bool:
        message = (
            "✅ Meeting Confirmed!\n"
            f"Company: {company_name}\n"
            f"Contact: {contact_name} ({contact_role})\n"
            f"Time: {scheduled_time}\n"
            f"Link: {meeting_link}"
        )
        return await self._send(self.admin_number, message)

    async def send_pre_meeting_briefing(
        self,
        company_name: str,
        briefing: dict,
        meeting_link: str | None = None,
    ) -> bool:
        """The T-30min admin message — a script to read, not a summary.

        `opening_line` and `objections` come from the Executive Whisperer
        upgrade in meeting_manager.build_whisper(); a briefing written before
        that (or by the keyless mock) simply omits those sections rather than
        rendering empty headings.
        """
        key_points = briefing.get("key_points") or []
        watch_out_for = briefing.get("watch_out_for") or []
        objections = [
            obj
            for obj in (briefing.get("objections") or [])
            if isinstance(obj, dict) and obj.get("objection")
        ]

        lines = [
            f"⏰ Meeting in 30 minutes — {company_name}",
            f"Problem: {briefing.get('customer_problem', 'n/a')}",
            f"Pitch: {briefing.get('recommended_service', 'n/a')}",
        ]

        if briefing.get("opening_line"):
            lines.append(f"\n🎤 Open with:\n\"{briefing['opening_line']}\"")

        if objections:
            rendered = "\n".join(
                f"- They say: {obj['objection']}\n  You say: "
                f"{obj.get('rebuttal') or '(no rebuttal drafted)'}"
                for obj in objections
            )
            lines.append(f"\n🛡 Objections:\n{rendered}")

        lines.append(
            "\nKey points:\n"
            + ("\n".join(f"- {point}" for point in key_points) or "- (none noted)")
        )
        lines.append(
            "Watch out:\n"
            + ("\n".join(f"- {item}" for item in watch_out_for) or "- (none noted)")
        )

        if meeting_link:
            lines.append(f"\nLink: {meeting_link}")

        return await self._send(self.admin_number, "\n".join(lines))

    async def send_audio_briefing(self, company_name: str, audio_path: str) -> bool:
        """Send the drive-time briefing to the admin as a WhatsApp voice note.

        Only Green API supports a file upload here; on Twilio the media has to
        be publicly reachable by URL first, which a localhost demo is not, so
        that transport reports False rather than pretending. Mock mode logs
        the path so a credential-free demo still shows the step happening.
        """
        caption = f"🎧 Drive-time briefing — {company_name}"

        if self.transport == "green_api":
            if not self.admin_number:
                _log.warning("Green API audio send skipped - no admin number configured")
                return False
            return await self._send_green_api_file(self.admin_number, audio_path, caption)

        if self.transport == "twilio":
            _log.warning(
                "Twilio transport cannot upload a local file - skipping the audio "
                "briefing (the text briefing was still sent)"
            )
            return False

        _log.info("MOCK WhatsApp audio send to %s: %s", self.admin_number or "(none)", audio_path)
        return True

    async def _send_green_api_file(
        self, to_number: str, file_path: str, caption: str
    ) -> bool:
        """POST an audio file to Green API's sendFileByUpload endpoint."""
        url = (
            f"{self.green_api_url}/waInstance{self.id_instance}"
            f"/sendFileByUpload/{self.token_instance}"
        )
        path = Path(file_path)
        try:
            audio = path.read_bytes()
        except OSError as exc:
            _log.error("Could not read audio briefing %s: %s", file_path, exc)
            return False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    data={
                        "chatId": _to_chat_id(to_number),
                        "caption": caption,
                        "fileName": path.name,
                    },
                    files={"file": (path.name, audio, "audio/mpeg")},
                )
                response.raise_for_status()
            _log.info("WhatsApp audio briefing sent via Green API to %s", to_number)
            return True
        except Exception as exc:  # noqa: BLE001 — comms layer must not crash the pipeline
            _log.error("Green API file send to %s failed: %s", to_number, exc)
            return False

    # -- company-facing (extra credit) ---------------------------------
    async def send_company_meeting_confirmation(
        self,
        to_number: str,
        company_name: str,
        contact_name: str,
        meeting_link: str,
        scheduled_time: str,
    ) -> bool:
        """Message the prospect directly on WhatsApp when their contact
        record has a phone number on file. Deliberately short and
        external-facing — no internal sales notes (objections, watch-outs)
        ever go to the prospect; that content is admin-only, via
        send_pre_meeting_briefing above."""
        message = (
            f"Hi {contact_name}! This confirms your meeting with "
            f"{settings.SENDER_COMPANY_NAME}.\n"
            f"Time: {scheduled_time}\n"
            f"Link: {meeting_link}\n\n"
            f"Looking forward to speaking with {company_name}!"
        )
        return await self._send(to_number, message)
