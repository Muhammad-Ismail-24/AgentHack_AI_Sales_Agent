"""
Sends personalised outreach emails via Resend and records every send in the
DB, regardless of outcome, so the pipeline always knows what was sent, when,
and to whom.

Runs in mock mode (logs the payload, returns a fake success) when
RESEND_API_KEY is not configured — see comms/_llm.py docstring for the same
pattern applied to the Anthropic client.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from comms._deps import crud, get_logger, settings

_log = get_logger("comms.email_sender")


class EmailSender:
    def __init__(self) -> None:
        self.api_key = settings.RESEND_API_KEY
        self.from_email = settings.SENDER_EMAIL or "sales@example.com"
        self.mock = not self.api_key

        self._resend = None
        if not self.mock:
            try:
                import resend

                resend.api_key = self.api_key
                self._resend = resend
            except ImportError:
                _log.warning("resend package not installed - falling back to MOCK MODE")
                self.mock = True

        if self.mock:
            _log.warning("RESEND_API_KEY not set - EmailSender running in MOCK MODE")

    async def send(self, to_email: str, subject: str, body: str, lead_id: str, contact_id: str) -> dict:
        if self.mock:
            fake_id = f"mock_{uuid.uuid4().hex[:12]}"
            _log.info(
                "MOCK send — to=%s subject=%r lead_id=%s contact_id=%s (resend_id=%s)",
                to_email,
                subject,
                lead_id,
                contact_id,
                fake_id,
            )
            result = {"success": True, "email_id": fake_id}
        else:
            try:
                params = {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": body,
                }
                # resend's SDK is synchronous — run it off the event loop so
                # it doesn't block the APScheduler jobs sharing this loop.
                response = await asyncio.to_thread(self._resend.Emails.send, params)
                resend_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
                _log.info("Email sent to %s (resend_id=%s)", to_email, resend_id)
                result = {"success": True, "email_id": resend_id}
            except Exception as exc:  # noqa: BLE001
                _log.error("Failed to send email to %s: %s", to_email, exc)
                result = {"success": False, "error": str(exc)}

        crud.create_email(
            lead_id=lead_id,
            contact_id=contact_id,
            subject=subject,
            body=body,
            status="sent" if result.get("success") else "failed",
            sent_at=datetime.now(timezone.utc),
        )
        return result
