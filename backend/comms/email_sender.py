"""
Sends personalised outreach emails and records every send in the DB,
regardless of outcome, so the pipeline always knows what was sent, when, and
to whom.

Three transports. SMTP is preferred where it works — Gmail SMTP avoids
Resend's free-tier restriction of only sending to your own verified address
— then Resend, then a mock that logs the payload so the demo and the comms
tests run with no credentials at all.

Which transport is used is decided per send, not once at construction,
because SMTP can be configured perfectly and still be unusable: many managed
hosts (Render included) firewall outbound ports 25/465/587 to curb spam, and
the connection fails with "[Errno 101] Network is unreachable" no matter how
correct the credentials are. Choosing at construction meant every send on
such a host failed forever with Resend sitting there configured and idle.
_send_via_smtp now reports whether it failed for a reason another attempt
could fix, and send() falls through to Resend when it did.

The public interface is unchanged: `await EmailSender().send(...)`.
"""

import asyncio
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from comms._deps import crud, get_logger, settings

_log = get_logger("comms.email_sender")


class EmailSender:
    def __init__(self) -> None:
        self.from_email = settings.sender_email or "sales@example.com"
        self.from_name = settings.SENDER_COMPANY_NAME

        self._resend = None
        self._smtp = bool(settings.smtp_configured)

        if settings.RESEND_API_KEY:
            try:
                import resend

                resend.api_key = settings.RESEND_API_KEY
                self._resend = resend
            except ImportError:
                _log.warning("resend package not installed - Resend unavailable")

        if self._smtp:
            _log.info(
                "EmailSender using SMTP %s:%s as %s%s",
                settings.SMTP_HOST, settings.SMTP_PORT, self.from_email,
                " (Resend available as a fallback)" if self._resend else "",
            )
        elif self._resend:
            _log.info("EmailSender using Resend as %s", self.from_email)
        else:
            _log.warning(
                "no SMTP or Resend credentials - EmailSender running in MOCK MODE"
            )

    @property
    def transport(self) -> str:
        """The transport a send would try first. Read by tests and /health."""
        if self._smtp:
            return "smtp"
        return "resend" if self._resend else "mock"

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

    async def _try_resend(self, to_email: str, subject: str, body: str) -> dict:
        try:
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": body.replace("\n", "<br>"),
            }
            response = await asyncio.to_thread(self._resend.Emails.send, params)
            resend_id = (
                response.get("id")
                if isinstance(response, dict)
                else getattr(response, "id", None)
            )
            _log.info("Email sent to %s (resend_id=%s)", to_email, resend_id)
            return {"success": True, "email_id": resend_id}
        except Exception as exc:  # noqa: BLE001
            _log.error("Resend send to %s failed: %s", to_email, exc)
            return {"success": False, "error": str(exc)}

    async def send(
        self, to_email: str, subject: str, body: str, lead_id: str, contact_id: str
    ) -> dict:
        result: dict | None = None

        if self._smtp:
            try:
                # smtplib is synchronous — keep it off the event loop shared
                # with the APScheduler jobs.
                message_id = await asyncio.to_thread(
                    self._send_smtp, to_email, subject, body
                )
                _log.info("Email sent to %s via SMTP (id=%s)", to_email, message_id)
                result = {"success": True, "email_id": message_id}
            except OSError as exc:
                # Connection-level failure — the host cannot reach the SMTP
                # port at all (Render and friends block them). Credentials are
                # not the problem, so retrying SMTP is pointless; Resend goes
                # out over HTTPS and is not blocked.
                if self._resend:
                    _log.warning(
                        "SMTP unreachable for %s (%s) — falling back to Resend. "
                        "Managed hosts commonly block outbound SMTP ports.",
                        to_email, exc,
                    )
                    result = await self._try_resend(to_email, subject, body)
                else:
                    _log.error(
                        "SMTP send to %s failed: %s. The host is likely blocking "
                        "outbound SMTP — set RESEND_API_KEY to send over HTTPS.",
                        to_email, exc,
                    )
                    result = {"success": False, "error": str(exc)}
            except Exception as exc:  # noqa: BLE001 - auth, recipient, etc.
                _log.error("SMTP send to %s failed: %s", to_email, exc)
                result = {"success": False, "error": str(exc)}

        elif self._resend:
            result = await self._try_resend(to_email, subject, body)

        else:
            fake_id = f"mock_{uuid.uuid4().hex[:12]}"
            _log.info(
                "MOCK send - to=%s subject=%r lead_id=%s contact_id=%s (id=%s)",
                to_email, subject, lead_id, contact_id, fake_id,
            )
            result = {"success": True, "email_id": fake_id}

        crud.create_email(
            lead_id=lead_id,
            contact_id=contact_id,
            subject=subject,
            body=body,
            status="sent" if result.get("success") else "failed",
            sent_at=datetime.now(timezone.utc),
        )
        return result
