"""Load the demo seed data into the database.

    python backend/load_seeds.py

Wipes every table first, so this is a development and demo tool only. Runs
synchronously — no event loop, no FastAPI, just the database.

Reads from data/seeds/:
    leads_seed.json     12 pre-researched leads with contacts   (Wajeeh)
    emails_seed.json    outreach already sent                   (Wajeeh)
    replies_seed.json   planted replies for the inbox demo      (Sufiyan)
    meetings_seed.json  a booked meeting with its briefing      (Sufiyan)

The two files Sufiyan owns are optional — if they are missing the script says
so and loads everything else. Relative dates (`sent_days_ago`,
`scheduled_in_days`) are resolved at load time so the demo is always "3 days
ago" rather than a date that goes stale.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.settings import settings  # noqa: E402
from db.database import Base, SyncSessionLocal, sync_engine  # noqa: E402
from db.models import (  # noqa: E402
    Contact,
    Email,
    Lead,
    Meeting,
    PipelineEvent,
    Reply,
)
from utils.logger import get_logger  # noqa: E402

log = get_logger("load_seeds")

SEED_DIR = Path(settings.SEED_DIR)
SESSION_ID = "demo-session"

# A reply's classification implies what the human should do next. Keeping this
# here rather than in the seed file means Sufiyan's file stays untouched.
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
    """Load a seed file, or return None if it isn't on this branch yet."""
    path = SEED_DIR / name
    if not path.exists():
        log.warning("%s not found — skipping", name)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name} is not valid JSON: {exc}") from exc


def clear_all(db) -> None:
    """Delete every row. Children first so foreign keys stay satisfied."""
    for model in (PipelineEvent, Reply, Meeting, Email, Contact, Lead):
        db.query(model).delete()
    db.commit()
    log.info("cleared existing data")


def load_leads(db, rows: list[dict]) -> tuple[int, int]:
    """Insert leads with their contacts and an opening timeline event."""
    lead_count = 0
    contact_count = 0

    for row in rows:
        contacts = row.pop("contacts", [])

        lead = Lead(
            id=row["id"],
            company_name=row["company_name"],
            website=row.get("website"),
            industry=row.get("industry"),
            location=row.get("location"),
            employee_count=row.get("employee_count"),
            pipeline_stage=row.get("pipeline_stage", "Discovered"),
            lead_score=row.get("lead_score"),
            score_explanation=row.get("score_explanation"),
            recommended_service=row.get("recommended_service"),
            pitch_angle=row.get("pitch_angle"),
            icp_fit=row.get("icp_fit"),
            research_summary=row.get("research_summary"),
            apollo_data=row.get("apollo_data"),
            session_id=SESSION_ID,
        )
        db.add(lead)
        lead_count += 1

        for index, raw in enumerate(contacts):
            db.add(
                Contact(
                    id=f"{lead.id}_contact_{index + 1}",
                    lead_id=lead.id,
                    name=raw.get("name"),
                    role=raw.get("role"),
                    email=raw.get("email"),
                    linkedin_url=raw.get("linkedin_url"),
                    is_primary=raw.get("is_primary", index == 0),
                )
            )
            contact_count += 1

        # Give every lead a plausible timeline rather than a single blank row.
        db.add(
            PipelineEvent(
                lead_id=lead.id,
                from_stage=None,
                to_stage="Discovered",
                reason="Lead discovered",
                created_at=_now() - timedelta(days=7),
            )
        )
        if lead.pipeline_stage != "Discovered":
            db.add(
                PipelineEvent(
                    lead_id=lead.id,
                    from_stage="Discovered",
                    to_stage=lead.pipeline_stage,
                    reason=lead.score_explanation
                    and f"Scored {lead.lead_score}/100"
                    or "Advanced by pipeline",
                    created_at=_now() - timedelta(days=5),
                )
            )

    db.commit()
    return lead_count, contact_count


def load_emails(db, rows: list[dict]) -> int:
    """Insert sent outreach, resolving contact_email to a real contact id."""
    count = 0

    for row in rows:
        contact_id = None
        if row.get("contact_email"):
            contact = (
                db.query(Contact)
                .filter(
                    Contact.lead_id == row["lead_id"],
                    Contact.email == row["contact_email"],
                )
                .first()
            )
            if contact is None:
                log.warning(
                    "no contact %s on %s — email will have no contact",
                    row["contact_email"],
                    row["lead_id"],
                )
            else:
                contact_id = contact.id

        sent_at = _now() - timedelta(days=row.get("sent_days_ago", 3))

        db.add(
            Email(
                id=row["id"],
                lead_id=row["lead_id"],
                contact_id=contact_id,
                subject=row["subject"],
                body=row["body"],
                status=row.get("status", "sent"),
                sent_at=sent_at if row.get("status", "sent") != "draft" else None,
                created_at=sent_at,
            )
        )
        count += 1

    db.commit()
    return count


def load_replies(db, rows: list[dict]) -> int:
    """Attach planted replies to the email they answer, by subject match."""
    count = 0

    for row in rows:
        # Sufiyan's file stores "Re: <original subject>".
        subject = row["subject"]
        original = subject[3:].strip() if subject.lower().startswith("re:") else subject

        email = (
            db.query(Email)
            .filter(Email.lead_id == row["lead_id"], Email.subject == original)
            .first()
        )
        if email is None:
            log.warning(
                "no sent email on %s matching %r — skipping reply",
                row["lead_id"],
                original,
            )
            continue

        classification = row.get("expected_classification") or row.get("classification")

        db.add(
            Reply(
                email_id=email.id,
                raw_body=row["body"],
                classification=classification,
                summary=SUMMARIES.get(classification),
                next_action=NEXT_ACTIONS.get(classification),
                received_at=_now() - timedelta(days=1),
            )
        )
        email.status = "replied"
        count += 1

    db.commit()
    return count


def load_meetings(db, rows: list[dict]) -> int:
    """Insert booked meetings, matching the contact by name where given."""
    count = 0

    for row in rows:
        contact_id = None
        if row.get("contact_name"):
            contact = (
                db.query(Contact)
                .filter(
                    Contact.lead_id == row["lead_id"],
                    Contact.name == row["contact_name"],
                )
                .first()
            )
            contact_id = contact.id if contact else None

        if row.get("scheduled_at"):
            scheduled_at = datetime.fromisoformat(
                row["scheduled_at"].replace("Z", "+00:00")
            )
            # A hardcoded date that has already passed makes the demo look
            # broken — pull it forward rather than showing a stale meeting.
            if scheduled_at < _now():
                log.warning(
                    "%s meeting was in the past — moving it to tomorrow",
                    row["lead_id"],
                )
                scheduled_at = _now() + timedelta(days=1)
        else:
            scheduled_at = _now() + timedelta(days=row.get("scheduled_in_days", 3))

        db.add(
            Meeting(
                lead_id=row["lead_id"],
                contact_id=contact_id,
                meeting_link=row.get("meeting_link"),
                scheduled_at=scheduled_at,
                briefing=row.get("briefing"),
                admin_notified=False,
                status=row.get("status", "confirmed"),
            )
        )
        count += 1

    db.commit()
    return count


def main() -> None:
    log.info("seeding from %s", SEED_DIR)

    leads = _read("leads_seed.json")
    if leads is None:
        raise SystemExit("leads_seed.json is required — nothing to load.")

    Base.metadata.create_all(sync_engine)

    with SyncSessionLocal() as db:
        clear_all(db)

        lead_count, contact_count = load_leads(db, leads)

        email_count = 0
        emails = _read("emails_seed.json")
        if emails:
            email_count = load_emails(db, emails)

        reply_count = 0
        replies = _read("replies_seed.json")
        if replies:
            reply_count = load_replies(db, replies)

        meeting_count = 0
        meetings = _read("meetings_seed.json")
        if meetings:
            meeting_count = load_meetings(db, meetings)

    print(
        f"Seed data loaded: {lead_count} leads, {contact_count} contacts, "
        f"{email_count} emails, {reply_count} replies, {meeting_count} meetings"
    )
    print(f"Session id: {SESSION_ID}")


if __name__ == "__main__":
    main()
