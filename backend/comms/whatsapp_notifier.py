"""
Sends admin-facing WhatsApp notifications via Twilio: a meeting-confirmed
alert (fired from meeting_manager.handle_meeting_request) and a 30-minute
pre-meeting briefing (fired from meeting_manager.send_pre_meeting_reminder).

Runs in mock mode (logs the message, returns True) when Twilio credentials
are incomplete or the twilio package isn't installed — same pattern as
EmailSender in email_sender.py.

Message templates match sufiyan_work.md's Step 6 spec verbatim, emoji
included. See utils/logger.py's _make_console_utf8_safe() for the UTF-8
console fix that keeps that content from mangling — or raising — in
mock-mode log output on Windows.
"""

import asyncio

from comms._deps import get_logger, settings

_log = get_logger("comms.whatsapp_notifier")


class WhatsAppNotifier:
    def __init__(self) -> None:
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_FROM
        self.admin_number = settings.ADMIN_WHATSAPP_NUMBER

        self.mock = not all(
            (self.account_sid, self.auth_token, self.from_number, self.admin_number)
        )

        self._client = None
        if not self.mock:
            try:
                from twilio.rest import Client

                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                _log.warning("twilio package not installed - falling back to MOCK MODE")
                self.mock = True

        if self.mock:
            _log.warning("Twilio credentials incomplete - WhatsAppNotifier running in MOCK MODE")

    async def _send(self, message: str) -> bool:
        if self.mock:
            _log.info(
                "MOCK WhatsApp send to %s:\n%s",
                self.admin_number or "(no ADMIN_WHATSAPP_NUMBER configured)",
                message,
            )
            return True

        try:
            # twilio's SDK is synchronous — run it off the event loop so it
            # doesn't block the scheduler jobs sharing this loop.
            await asyncio.to_thread(
                self._client.messages.create,
                from_=f"whatsapp:{self.from_number}",
                to=f"whatsapp:{self.admin_number}",
                body=message,
            )
            _log.info("WhatsApp message sent to admin (%s)", self.admin_number)
            return True
        except Exception as exc:  # noqa: BLE001 — comms layer must not crash the pipeline
            _log.error("Failed to send WhatsApp message: %s", exc)
            return False

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
        return await self._send(message)

    async def send_pre_meeting_briefing(self, company_name: str, briefing: dict) -> bool:
        key_points = briefing.get("key_points") or []
        watch_out_for = briefing.get("watch_out_for") or []
        key_points_str = "\n".join(f"- {point}" for point in key_points) or "- (none noted)"
        watch_out_str = "\n".join(f"- {item}" for item in watch_out_for) or "- (none noted)"

        message = (
            f"⏰ Meeting in 30 minutes — {company_name}\n"
            f"Problem: {briefing.get('customer_problem', 'n/a')}\n"
            f"Pitch: {briefing.get('recommended_service', 'n/a')}\n"
            f"Key points:\n{key_points_str}\n"
            f"Watch out:\n{watch_out_str}"
        )
        return await self._send(message)
