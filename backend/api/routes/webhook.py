"""
POST /webhook/email-reply — Sufiyan's full ownership per sufiyan_work.md,
inside a directory (backend/api/routes/) whose FOLDER_STRUCTURE.md-level
ownership is Wajeeh's. sufiyan_work.md is the more specific assignment for
this one file, so it's honored here.

Registration note: the "/webhook" prefix is applied where this router is
included (backend/main.py, per Step 7 of sufiyan_work.md:
  app.include_router(webhook_router, prefix="/webhook")
), which doesn't exist yet in this branch — see conflicts.md.

Payload parsing is deliberately lenient. Resend's inbound-email webhook
shape isn't validated against live docs here (no network access / no
example payload on file), and the handler must NEVER fail — a broken or
unexpected payload should still return 200, per spec, so a malformed
delivery doesn't get retried forever by the sender. A strict Pydantic
schema (once backend/api/schemas.py exists, see conflicts.md) can replace
this once the real Resend payload shape is confirmed against their docs.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from comms._deps import get_logger
from comms.email_reader import EmailReader

router = APIRouter()
_log = get_logger("api.webhook")


def _extract_from_email(data: dict) -> str:
    """Best-effort extraction across the shapes Resend's inbound payload
    might take: a plain string, an object with "email", or a
    "Name <email@x.com>" formatted string."""
    from_field = data.get("from")
    if isinstance(from_field, dict):
        from_field = from_field.get("email") or from_field.get("address") or ""
    from_field = from_field or ""

    if "<" in from_field and ">" in from_field:
        return from_field.split("<", 1)[1].split(">", 1)[0].strip()
    return from_field.strip()


@router.post("/email-reply")
async def email_reply_webhook(request: Request) -> dict:
    try:
        payload = await request.json()
        data = payload.get("data", payload)  # tolerate both {"data": {...}} and a flat body

        from_email = _extract_from_email(data)
        subject = data.get("subject", "") or ""
        body = data.get("text") or data.get("body") or data.get("html") or ""
        timestamp = (
            data.get("created_at")
            or data.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        )

        result = await EmailReader().process_inbound_reply(
            from_email=from_email,
            subject=subject,
            body=body,
            timestamp=timestamp,
        )
        _log.info(
            "Webhook processed inbound reply: matched=%s classification=%s",
            result["matched"],
            result["classification"],
        )
    except Exception as exc:  # noqa: BLE001 — webhook must never fail (always return 200)
        _log.error("Failed to process inbound webhook payload: %s", exc)

    return {"status": "ok"}
