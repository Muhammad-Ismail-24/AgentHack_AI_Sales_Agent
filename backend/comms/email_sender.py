"""
Sends personalised outreach emails and records every send in the DB,
regardless of outcome, so the pipeline always knows what was sent, when, and
to whom.

Three transports, tried in order at construction time:

  1. SMTP (settings.SMTP_HOST/USER/PASSWORD) — the active path. Gmail SMTP
     avoids Resend's free-tier restriction of only sending to your own
     verified address.
  2. Resend (settings.RESEND_API_KEY) — kept as an alternative.
  3. Mock — logs the payload and returns a fake success, so the demo and the
     comms tests run with no credentials at all.

The public interface is unchanged: `await EmailSender().send(...)`.

The Resend path is throttled through a module-level TokenBucket
(settings.RESEND_RPM) — see utils/rate_limiter.py. SMTP and mock aren't
gated; Resend is the transport with a documented external rate limit.
"""

import asyncio
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from comms._deps import crud, get_logger, settings
from utils.rate_limiter import TokenBucket

_log = get_logger("comms.email_sender")
_resend_bucket = TokenBucket(settings.RESEND_RPM)


class EmailSender:
    def __init__(self) -> None:
        self.from_email = settings.sender_email or "sales@example.com"
        self.from_name = settings.SENDER_COMPANY_NAME

        self.transport = "mock"
        self._resend = None

        if settings.smtp_configured:
            self.transport = "smtp"
            _log.info(
                "EmailSender using SMTP %s:%s as %s",
                settings.SMTP_HOST, settings.SMTP_PORT, self.from_email,
            )

        elif settings.RESEND_API_KEY:
            try:
                import resend

                resend.api_key = settings.RESEND_API_KEY
                self._resend = resend
                self.transport = "resend"
                _log.info("EmailSender using Resend as %s", self.from_email)
            except ImportError:
                _log.warning("resend package not installed - falling back to MOCK MODE")

        if self.transport == "mock":
            _log.warning(
                "no SMTP or Resend credentials - EmailSender running in MOCK MODE"
            )

    @property
    def mock(self) -> bool:
        """Kept as a property so existing callers and tests still read it."""
        return self.transport == "mock"

    def _send_smtp(self, to_email: str, subject: str, body: str) -> str:
        """Blocking SMTP send. Called via asyncio.to_thread."""
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((self.from_name, self.from_email))
        message["To"] = to_email
        # Plain text is the body the agents write; the HTML part keeps the
        # line breaks intact in clients that prefer HTML.
        message.set_content(body)
        message.add_alternative(
            "<html><body>"
            + body.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
            + "</body></html>",
            subtype="html",
        )

        port = int(settings.SMTP_PORT or 587)
        if port == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, port, timeout=30) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)

        return message.get("Message-ID") or f"smtp_{uuid.uuid4().hex[:12]}"

    async def send(
        self, to_email: str, subject: str, body: str, lead_id: str, contact_id: str
    ) -> dict:
        if self.transport == "mock":
            fake_id = f"mock_{uuid.uuid4().hex[:12]}"
            _log.info(
                "MOCK send - to=%s subject=%r lead_id=%s contact_id=%s (id=%s)",
                to_email, subject, lead_id, contact_id, fake_id,
            )
            result = {"success": True, "email_id": fake_id}

        elif self.transport == "smtp":
            try:
                # smtplib is synchronous — keep it off the event loop shared
                # with the APScheduler jobs.
                message_id = await asyncio.to_thread(
                    self._send_smtp, to_email, subject, body
                )
                _log.info("Email sent to %s via SMTP (id=%s)", to_email, message_id)
                result = {"success": True, "email_id": message_id}
            except Exception as exc:  # noqa: BLE001
                _log.error("SMTP send to %s failed: %s", to_email, exc)
                result = {"success": False, "error": str(exc)}

        else:  # resend
            try:
                params = {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": body.replace("\n", "<br>"),
                }
                await _resend_bucket.acquire()
                response = await asyncio.to_thread(self._resend.Emails.send, params)
                resend_id = (
                    response.get("id")
                    if isinstance(response, dict)
                    else getattr(response, "id", None)
                )
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
