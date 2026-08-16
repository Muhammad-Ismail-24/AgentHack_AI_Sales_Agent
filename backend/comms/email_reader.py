"""
Processes inbound email replies: matches a reply to the original outbound
email, records it, classifies it, and dispatches the next pipeline action.

Matching strategy, per sufiyan_work.md Step 4:
  1. Subject match — strip any "Re:" prefix(es) and compare against stored
     outbound email subjects.
  2. Fallback — match from_email against a known contact, then take that
     contact's most recently sent email.

Note on CLAUDE.md's "Agents must never import from comms/ directly — go
through the orchestrator": that rule governs backend/agents/* reaching
into comms/, not comms modules composing each other. EmailReader calling
MeetingManager below is comms -> comms, which is exactly how
sufiyan_work.md specifies this step, and doesn't create an import cycle
(meeting_manager.py never imports email_reader).
"""

import re
from datetime import datetime, timezone
from typing import Optional

from comms._deps import crud, get_logger
from comms.meeting_manager import MeetingManager
from comms.response_classifier import ResponseClassifier

_log = get_logger("comms.email_reader")

_RE_PREFIX = re.compile(r"^(re:\s*)+", re.IGNORECASE)


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return datetime.now(timezone.utc)


class EmailReader:
    def __init__(self) -> None:
        self._classifier = ResponseClassifier()

    def _find_original_email(self, from_email: str, subject: str) -> Optional[dict]:
        clean_subject = _RE_PREFIX.sub("", subject or "").strip().lower()

        if clean_subject:
            for email in crud.get_all_emails():
                if email["subject"].strip().lower() == clean_subject:
                    return email

        contact = crud.get_contact_by_email(from_email)
        if contact is not None:
            candidates = [e for e in crud.get_all_emails() if e["contact_id"] == contact["id"]]
            if candidates:
                return max(candidates, key=lambda e: e["sent_at"])

        return None

    async def process_inbound_reply(self, from_email: str, subject: str, body: str, timestamp: str) -> dict:
        original_email = self._find_original_email(from_email, subject)
        if original_email is None:
            _log.warning(
                "No matching outbound email for reply from %s (subject=%r) - dropping",
                from_email,
                subject,
            )
            return {"matched": False, "classification": None, "next_action": None}

        # Stored before classifying so the reply survives even if the LLM
        # call fails; the verdict is written back onto this row below.
        reply = crud.create_reply(
            email_id=original_email["id"],
            raw_body=body,
            received_at=_parse_timestamp(timestamp),
        )
        crud.update_email_status(original_email["id"], "replied")

        lead = crud.get_lead(original_email["lead_id"])
        company_name = lead["company_name"] if lead else original_email["lead_id"]

        classification_result = await self._classifier.classify(
            reply_body=body,
            original_subject=original_email["subject"],
            company_name=company_name,
        )
        classification = classification_result["classification"]
        next_action = await self._classifier.decide_next_action(classification, original_email["lead_id"])

        # Write the verdict back onto the stored reply. Without this the
        # classifier's work only ever existed in this function's locals: the
        # reply row kept the nulls it was created with, so the Inbox listed
        # every reply as unclassified with no next action, even when the
        # meeting it triggered had already been booked.
        if reply and reply.get("id"):
            crud.update_reply_classification(
                reply["id"],
                classification,
                summary=classification_result.get("summary"),
                next_action=next_action,
            )

        if next_action == "send_meeting_link":
            await MeetingManager().handle_meeting_request(original_email["lead_id"])

        _log.info(
            "Processed reply from %s: classification=%s next_action=%s",
            from_email,
            classification,
            next_action,
        )
        return {"matched": True, "classification": classification, "next_action": next_action}
