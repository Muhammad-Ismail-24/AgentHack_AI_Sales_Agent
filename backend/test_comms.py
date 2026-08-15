"""
End-to-end smoke test for the comms layer built so far (Steps 1-5).

Run from backend/:
    python test_comms.py

Works with zero API keys configured (everything runs in mock mode) and
gets more meaningful the more real keys you add. See conflicts.md for what
still depends on Wajeeh's backend/db/crud.py landing.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from comms._deps import USING_REAL_BACKEND, crud, get_logger
from comms._llm import is_mock_mode
from comms.email_reader import EmailReader
from comms.email_sender import EmailSender
from comms.followup_scheduler import check_and_send_followups, check_pre_meeting_reminders
from comms.meeting_manager import (
    _USING_REAL_CALENDAR_TOOL,
    _USING_REAL_WHATSAPP_NOTIFIER,
    MeetingManager,
)
from comms.response_classifier import ResponseClassifier

_log = get_logger("test_comms")

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"


def _banner() -> None:
    print("=" * 70)
    print("COMMS LAYER SMOKE TEST")
    print(f"  dependency source   : {'REAL backend' if USING_REAL_BACKEND else 'shim (comms/_shim.py)'}")
    print(f"  Claude (anthropic)  : {'MOCK' if is_mock_mode() else 'LIVE'}")
    print(f"  Resend              : {'MOCK' if EmailSender().mock else 'LIVE'}")
    print(f"  tools.calendar_tool : {'REAL' if _USING_REAL_CALENDAR_TOOL else 'MOCK (Ismail not landed yet)'}")
    print(f"  whatsapp_notifier   : {'REAL' if _USING_REAL_WHATSAPP_NOTIFIER else 'STUB (Step 6 not built yet)'}")
    print("=" * 70)


async def test_classification() -> None:
    print("\n--- 1. Response classification (data/seeds/replies_seed.json) ---")
    replies = json.loads((SEEDS_DIR / "replies_seed.json").read_text())
    classifier = ResponseClassifier()

    for reply in replies:
        lead = crud.get_lead(reply["lead_id"])
        company_name = lead["company_name"] if lead else reply["lead_id"]

        result = await classifier.classify(
            reply_body=reply["body"],
            original_subject=reply["subject"],
            company_name=company_name,
        )
        expected = reply["expected_classification"]
        actual = result["classification"]
        match = "yes" if actual == expected else "no"

        print(f"  {company_name:16s} expected={expected!r:22s} actual={actual!r:22s} match={match}")

        action = await classifier.decide_next_action(actual, reply["lead_id"])
        print(f"  {'':16s} -> next_action = {action}")


async def test_email_reader() -> None:
    print("\n--- 2. Email reader / inbound webhook simulation ---")
    sender = EmailSender()
    reader = EmailReader()

    lead_id = "lead_002"
    lead = crud.get_lead(lead_id)
    contact = crud.get_primary_contact(lead_id)
    subject = "Cut Response Time by 60% - BetaFreight"

    # Send an outbound email first, so there's something for the inbound
    # reply below to match against (subject match, per EmailReader step 1).
    await sender.send(
        to_email=contact["email"],
        subject=subject,
        body="Hi, we help teams like yours cut support response time by 60%...",
        lead_id=lead_id,
        contact_id=contact["id"],
    )

    result = await reader.process_inbound_reply(
        from_email=contact["email"],
        subject=f"Re: {subject}",
        body="What's the pricing for a team of 30?",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    print(f"  Simulated reply from {contact['email']} (subject match against {lead['company_name']})")
    print(f"  matched={result['matched']} classification={result['classification']!r} next_action={result['next_action']!r}")


async def test_meeting_flow() -> None:
    print("\n--- 3. Meeting request flow ---")
    manager = MeetingManager()
    result = await manager.handle_meeting_request("lead_001")
    print(f"  meeting_link  = {result['meeting_link']}")
    print(f"  email_sent    = {result['email_sent']}")
    print(f"  WhatsApp sent = {result['whatsapp_sent']}")


async def test_pre_meeting_reminder() -> None:
    print("\n--- 4. Pre-meeting reminder (35-minute window) ---")
    # Create a meeting scheduled 20 minutes out so it falls inside the
    # reminder window, then run the same job the scheduler runs every 5min.
    meeting = crud.create_meeting(
        lead_id="lead_001",
        contact_id=crud.get_primary_contact("lead_001")["id"],
        meeting_link="https://cal.com/admin/alphalogistics-demo",
        status="link_sent",
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=20),
    )
    sent = await check_pre_meeting_reminders()
    refreshed = crud.get_meeting(meeting["id"])
    print(f"  Reminders sent this run : {sent}")
    print(f"  meeting.admin_notified  : {refreshed['admin_notified']}")


async def test_followup_scheduler() -> None:
    print("\n--- 5. Follow-up scheduler ---")
    candidates_before = crud.get_emails_needing_followup(days=3)
    print(f"  Emails currently qualifying for a 3-day follow-up: {len(candidates_before)}")
    if not candidates_before:
        print("  (expected - the emails sent above were just sent, not 3+ days old)")

    sent = await check_and_send_followups()
    print(f"  Follow-ups actually sent this run: {sent}")


async def main() -> None:
    _banner()
    await test_classification()
    await test_email_reader()
    await test_meeting_flow()
    await test_pre_meeting_reminder()
    await test_followup_scheduler()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
