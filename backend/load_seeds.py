"""Load the demo seed data into Firestore.

    python backend/load_seeds.py

Wipes every collection first, so this is a development and demo tool only.

Reads from data/seeds/:
    leads_seed.json     12 pre-researched leads with contacts
    emails_seed.json    outreach already sent
    replies_seed.json   planted replies for the inbox demo
    meetings_seed.json  a booked meeting with its briefing

Relative dates (`sent_days_ago`, `scheduled_in_days`) are resolved at load
time so the demo always reads as "3 days ago" rather than a date that goes
stale.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.settings import settings  # noqa: E402
from db import crud, firestore as fs  # noqa: E402
from db.models import (  # noqa: E402
    contact_doc,
    email_doc,
    event_doc,
    lead_doc,
    meeting_doc,
    reply_doc,
)
from utils.logger import get_logger  # noqa: E402

log = get_logger("load_seeds")

SEED_DIR = Path(settings.SEED_DIR)
SESSION_ID = "demo-session"

# A reply's classification implies what the human should do next.
NEXT_ACTIONS = {
    "Meeting Requested": "Send a Cal.com booking link today.",
    "Interested": "Send the case study deck and propose two times.",
    "Pricing Objection": "Reply with per-ticket pricing, not per-seat.",
    "Not Interested": "Mark do-not-contact and revisit in two quarters.",
    "Out of Office": "Hold and retry after their return date.",
    "Unclear": "Read the thread and reply manually.",
}

SUMMARIES = {
    "Meeting Requested": "Wants a call this week — WhatsApp volume is hurting.",
    "Pricing Objection": "Engaged, but wants pricing for a 30-person team first.",
    "Not Interested": "Declined outright, no reason given.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read(name: str) -> list | None:
    path = SEED_DIR / name
    if not path.exists():
        log.warning("%s not found — skipping", name)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name} is not valid JSON: {exc}") from exc


def _write(collection: str, doc: dict) -> dict:
    fs.collection(collection).document(doc["id"]).set(doc)
    return doc


def load_leads(rows: list[dict]) -> tuple[int, int]:
    lead_count = 0
    contact_count = 0

    for row in rows:
        row = dict(row)
        contacts = row.pop("contacts", [])
        row["session_id"] = SESSION_ID

        lead = lead_doc(row, doc_id=row["id"])
        _write(fs.LEADS, lead)
        lead_count += 1

        for index, raw in enumerate(contacts):
            contact = contact_doc(
                raw, lead["id"], doc_id=f"{lead['id']}_contact_{index + 1}"
            )
            contact["is_primary"] = raw.get("is_primary", index == 0)
            _write(fs.CONTACTS, contact)
            contact_count += 1

        # Give every lead a plausible timeline rather than one blank row.
        _write(
            fs.PIPELINE_EVENTS,
            event_doc(
                lead["id"], None, "Discovered", "Lead discovered",
                created_at=_now() - timedelta(days=7),
            ),
        )
        if lead["pipeline_stage"] != "Discovered":
            reason = (
                f"Scored {lead['lead_score']}/100"
                if lead.get("lead_score") is not None
                else "Advanced by pipeline"
            )
            _write(
                fs.PIPELINE_EVENTS,
                event_doc(
                    lead["id"], "Discovered", lead["pipeline_stage"], reason,
                    created_at=_now() - timedelta(days=5),
                ),
            )

    return lead_count, contact_count


def load_emails(rows: list[dict]) -> int:
    count = 0

    for row in rows:
        contact_id = None
        if row.get("contact_email"):
            for contact in crud.get_contacts_for_lead(row["lead_id"]):
                if (contact.get("email") or "").lower() == row["contact_email"].lower():
                    contact_id = contact["id"]
                    break
            if contact_id is None:
                log.warning(
                    "no contact %s on %s — email will have no contact",
                    row["contact_email"], row["lead_id"],
                )

        sent_at = _now() - timedelta(days=row.get("sent_days_ago", 3))
        status = row.get("status", "sent")

        _write(
            fs.EMAILS,
            email_doc(
                lead_id=row["lead_id"],
                contact_id=contact_id,
                subject=row["subject"],
                body=row["body"],
                status=status,
                sent_at=sent_at if status != "draft" else None,
                doc_id=row["id"],
                created_at=sent_at,
            ),
        )
        count += 1

    return count


def load_replies(rows: list[dict]) -> int:
    count = 0

    for row in rows:
        # The seed stores "Re: <original subject>".
        subject = row["subject"]
        original = subject[3:].strip() if subject.lower().startswith("re:") else subject

        email = next(
            (
                e
                for e in crud.get_emails_for_lead(row["lead_id"])
                if (e.get("subject") or "") == original
            ),
            None,
        )
        if email is None:
            log.warning(
                "no sent email on %s matching %r — skipping reply",
                row["lead_id"], original,
            )
            continue

        classification = row.get("expected_classification") or row.get("classification")

        _write(
            fs.REPLIES,
            reply_doc(
                email_id=email["id"],
                raw_body=row["body"],
                classification=classification,
                summary=SUMMARIES.get(classification),
                next_action=NEXT_ACTIONS.get(classification),
                received_at=_now() - timedelta(days=1),
            ),
        )
        fs.collection(fs.EMAILS).document(email["id"]).update({"status": "replied"})
        count += 1

    return count


def load_meetings(rows: list[dict]) -> int:
    count = 0

    for row in rows:
        contact_id = None
        if row.get("contact_name"):
            for contact in crud.get_contacts_for_lead(row["lead_id"]):
                if contact.get("name") == row["contact_name"]:
                    contact_id = contact["id"]
                    break

        if row.get("scheduled_at"):
            scheduled_at = datetime.fromisoformat(
                row["scheduled_at"].replace("Z", "+00:00")
            )
            # A hardcoded date that has already passed makes the demo look
            # broken — pull it forward rather than showing a stale meeting.
            if scheduled_at < _now():
                log.warning(
                    "%s meeting was in the past — moving it to tomorrow", row["lead_id"]
                )
                scheduled_at = _now() + timedelta(days=1)
        else:
            scheduled_at = _now() + timedelta(days=row.get("scheduled_in_days", 3))

        _write(
            fs.MEETINGS,
            meeting_doc(
                lead_id=row["lead_id"],
                contact_id=contact_id,
                meeting_link=row.get("meeting_link"),
                scheduled_at=scheduled_at,
                briefing=row.get("briefing"),
                status=row.get("status", "confirmed"),
            ),
        )
        count += 1

    return count


def main() -> None:
    log.info("seeding from %s", SEED_DIR)

    leads = _read("leads_seed.json")
    if leads is None:
        raise SystemExit("leads_seed.json is required — nothing to load.")

    try:
        fs.get_client()
    except fs.FirestoreUnavailable as exc:
        raise SystemExit(f"\n{exc}\n") from exc

    crud.clear_all()

    lead_count, contact_count = load_leads(leads)

    emails = _read("emails_seed.json")
    email_count = load_emails(emails) if emails else 0

    replies = _read("replies_seed.json")
    reply_count = load_replies(replies) if replies else 0

    meetings = _read("meetings_seed.json")
    meeting_count = load_meetings(meetings) if meetings else 0

    print(
        f"Seed data loaded: {lead_count} leads, {contact_count} contacts, "
        f"{email_count} emails, {reply_count} replies, {meeting_count} meetings"
    )
    print(f"Session id: {SESSION_ID}")


if __name__ == "__main__":
    main()
