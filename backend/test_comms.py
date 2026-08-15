"""
End-to-end test suite for the full comms layer — sufiyan_work.md Steps 1-9.

Run from backend/:
    python test_comms.py

Unlike a plain demo script, every step below makes real assertions and a
failure in one step is caught, recorded, and doesn't stop the rest of the
suite from running — the script always reaches the final PASS/FAIL
summary table, and exits non-zero only if something actually failed
("Flag any errors" per sufiyan_work.md's Step 9 spec).

Gets more meaningful the more real keys you add — LLM and email calls fall
back to mock mode without them. It does, however, need Firestore
(FIREBASE_SERVICE_ACCOUNT_PATH) and the seeded demo data, since it asserts
against real lead/contact/email records:

    python backend/load_seeds.py && cd backend && python test_comms.py
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, List

from api.routes.emails import SendEmailRequest, list_emails, send_email
from api.routes.meetings import CreateMeetingRequest, create_meeting, list_meetings
from comms._deps import USING_FIRESTORE, USING_REAL_BACKEND, crud, get_logger
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
from comms.whatsapp_notifier import WhatsAppNotifier

_log = get_logger("test_comms")

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"

VALID_CLASSIFICATIONS = {
    "Interested",
    "Meeting Requested",
    "Question",
    "Pricing Objection",
    "Technical Objection",
    "Not Interested",
    "Not Now",
    "Wrong Person",
    "Other",
}

# Full routing table from response_classifier.decide_next_action() — the 3
# seed replies only organically cover 3 of these 9 categories, so Step 2's
# test also exercises decide_next_action() directly for all 9.
EXPECTED_ROUTING = {
    "Interested": "stage_updated",
    "Meeting Requested": "send_meeting_link",
    "Question": "queue_for_review",
    "Pricing Objection": "queue_for_review",
    "Technical Objection": "queue_for_review",
    "Not Interested": "stop",
    "Not Now": "followup_scheduled",
    "Wrong Person": "find_new_contact",
    "Other": "queue_for_review",
}


@dataclass
class StepResult:
    step: int
    name: str
    passed: bool
    detail: str = ""


RESULTS: List[StepResult] = []


def _dependency_source_label() -> str:
    if USING_REAL_BACKEND:
        return "REAL backend (config/settings.py + utils/logger.py + db/crud.py on Firestore)"
    # The temporary stand-ins this used to describe are gone; comms now always
    # resolves to the real backend. Reaching here means _deps.py is broken.
    return "UNKNOWN - comms/_deps.py did not resolve the real backend"


def _banner() -> None:
    print("=" * 70)
    print("COMMS LAYER TEST SUITE - Steps 1-9")
    print(f"  dependency source   : {_dependency_source_label()}")
    print(f"  Gemini              : {'MOCK' if is_mock_mode() else 'LIVE'}")
    print(f"  email transport     : {EmailSender().transport.upper()}")
    print(f"  tools.calendar_tool : {'REAL' if _USING_REAL_CALENDAR_TOOL else 'MOCK (Ismail not landed yet)'}")
    print(f"  whatsapp_notifier   : {'REAL module' if _USING_REAL_WHATSAPP_NOTIFIER else 'STUB'}, Twilio client = {'MOCK' if WhatsAppNotifier().mock else 'LIVE'}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Step 1 — Email Sender
# ---------------------------------------------------------------------------
async def test_email_sender() -> None:
    contact = crud.get_primary_contact("lead_003")
    before_count = len(crud.get_all_emails())

    result = await EmailSender().send(
        to_email=contact["email"],
        subject="Welcome - GammaSupply",
        body="Hi, excited to work with you.",
        lead_id="lead_003",
        contact_id=contact["id"],
    )
    print(f"  EmailSender().send() -> success={result.get('success')} email_id={result.get('email_id')}")
    assert result.get("success") is True, f"send() reported failure: {result.get('error')}"

    after_emails = crud.get_all_emails()
    assert len(after_emails) == before_count + 1, "no new email record created in crud"
    assert after_emails[-1]["status"] == "sent"
    print(f"  DB record created: status={after_emails[-1]['status']!r} subject={after_emails[-1]['subject']!r}")


# ---------------------------------------------------------------------------
# Step 2 — Response Classifier (all 9 categories)
# ---------------------------------------------------------------------------
async def test_classification() -> None:
    replies = json.loads((SEEDS_DIR / "replies_seed.json").read_text())
    classifier = ResponseClassifier()
    match_count = 0

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
        match = actual == expected
        match_count += int(match)
        print(f"  {company_name:16s} expected={expected!r:22s} actual={actual!r:22s} match={'yes' if match else 'no'}")

        action = await classifier.decide_next_action(actual, reply["lead_id"])
        print(f"  {'':16s} -> next_action = {action}")

    assert match_count == len(replies), f"only {match_count}/{len(replies)} seed replies classified correctly"

    print(f"  Verifying decide_next_action() routing for all {len(EXPECTED_ROUTING)} categories directly:")
    for category, expected_action in EXPECTED_ROUTING.items():
        actual_action = await classifier.decide_next_action(category, "lead_001")
        ok = actual_action == expected_action
        print(f"    {category:20s} -> {actual_action:20s} ({'ok' if ok else 'MISMATCH'})")
        assert ok, f"{category!r} routed to {actual_action!r}, expected {expected_action!r}"


# ---------------------------------------------------------------------------
# Step 3 — Follow-Up Scheduler
# ---------------------------------------------------------------------------
async def test_followup_scheduler() -> None:
    contact = crud.get_primary_contact("lead_003")
    stale_email = crud.create_email(
        lead_id="lead_003",
        contact_id=contact["id"],
        subject="Stale Outreach - GammaSupply",
        body="First outreach that never got a reply.",
        status="sent",
        sent_at=datetime.now(timezone.utc) - timedelta(days=4),
    )

    candidates = crud.get_emails_needing_followup(days=3)
    print(f"  Emails qualifying for a 3-day follow-up before running the job: {len(candidates)}")
    assert any(e["id"] == stale_email["id"] for e in candidates), "4-day-old email not detected as needing follow-up"

    sent = await check_and_send_followups()
    print(f"  Follow-ups sent this run: {sent}")
    assert sent == 1, f"expected exactly 1 follow-up to be sent, got {sent}"

    candidates_after = crud.get_emails_needing_followup(days=3)
    still_qualifies = any(e["id"] == stale_email["id"] for e in candidates_after)
    print(f"  Same email still qualifies after follow-up sent: {still_qualifies} (should be False)")
    assert not still_qualifies, "email still qualifies for follow-up after one was already sent (not idempotent)"


# ---------------------------------------------------------------------------
# Step 4 — Email Reader / Inbound Webhook Matching
# ---------------------------------------------------------------------------
async def test_email_reader() -> None:
    sender = EmailSender()
    reader = EmailReader()

    lead_id = "lead_002"
    lead = crud.get_lead(lead_id)
    contact = crud.get_primary_contact(lead_id)
    subject = "Cut Response Time by 60% - BetaFreight"

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
    assert result["matched"] is True, "email_reader failed to match the inbound reply to its outbound email"
    assert result["classification"] in VALID_CLASSIFICATIONS

    unmatched = await reader.process_inbound_reply(
        from_email="nobody@unknown-domain.example",
        subject="Re: Something we never sent",
        body="huh?",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    print(f"  Unmatched-sender case handled cleanly: matched={unmatched['matched']} (should be False)")
    assert unmatched["matched"] is False, "email_reader should report matched=False for an unrecognized sender/subject"


# ---------------------------------------------------------------------------
# Step 5 — Meeting Manager
# ---------------------------------------------------------------------------
async def test_meeting_flow() -> None:
    manager = MeetingManager()
    result = await manager.handle_meeting_request("lead_001")
    print(f"  meeting_link  = {result['meeting_link']}")
    print(f"  email_sent    = {result['email_sent']}")
    print(f"  WhatsApp sent = {result['whatsapp_sent']}")
    assert result["meeting_link"], "handle_meeting_request produced no meeting_link"
    assert result["email_sent"] is True
    assert result["whatsapp_sent"] is True

    meeting = crud.create_meeting(
        lead_id="lead_001",
        contact_id=crud.get_primary_contact("lead_001")["id"],
        meeting_link="https://cal.com/admin/alphalogistics-demo",
        status="link_sent",
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=20),
    )
    sent = await check_pre_meeting_reminders()
    refreshed = crud.get_meeting(meeting["id"])
    print(f"  Pre-meeting reminders sent this run : {sent}")
    print(f"  meeting.admin_notified              : {refreshed['admin_notified']}")
    assert sent >= 1, "no pre-meeting reminder was sent for a meeting inside the 35-minute window"
    assert refreshed["admin_notified"] is True


# ---------------------------------------------------------------------------
# Step 6 — WhatsApp Notifier
# ---------------------------------------------------------------------------
async def test_whatsapp_notifier() -> None:
    notifier = WhatsAppNotifier()
    print(f"  Twilio client mode: {'MOCK' if notifier.mock else 'LIVE'}")

    confirmed = await notifier.send_meeting_confirmed(
        company_name="TestCo",
        contact_name="Jane Doe",
        contact_role="COO",
        meeting_link="https://cal.com/admin/testco",
        scheduled_time="tomorrow 3pm",
    )
    briefing_sent = await notifier.send_pre_meeting_briefing(
        company_name="TestCo",
        briefing={
            "customer_problem": "slow support",
            "recommended_service": "AI chatbot",
            "key_points": ["point A"],
            "watch_out_for": ["risk A"],
        },
    )
    print(f"  send_meeting_confirmed()    -> {confirmed}")
    print(f"  send_pre_meeting_briefing() -> {briefing_sent}")
    assert confirmed is True
    assert briefing_sent is True

    assert _USING_REAL_WHATSAPP_NOTIFIER is True, (
        "meeting_manager.py is still using the Step 6 stub, not the real "
        "comms.whatsapp_notifier module"
    )
    print("  Confirmed: meeting_manager.py is using the REAL whatsapp_notifier module (not the Step 6 stub)")


# ---------------------------------------------------------------------------
# Step 7 — API Routes (emails.py, meetings.py, webhook.py)
# ---------------------------------------------------------------------------
async def test_api_routes() -> None:
    emails_before = await list_emails()
    meetings_before = await list_meetings()
    print(f"  GET /emails   -> {len(emails_before)} email(s) on record")
    print(f"  GET /meetings -> {len(meetings_before)} meeting(s) on record")

    contact = crud.get_primary_contact("lead_003")
    send_result = await send_email(
        SendEmailRequest(
            lead_id="lead_003",
            contact_id=contact["id"],
            subject="Following up - GammaSupply",
            body="Just checking in - happy to answer any questions.",
        )
    )
    print(f"  POST /emails/send     -> success={send_result.success} message={send_result.message!r}")
    assert send_result.success is True

    create_result = await create_meeting(CreateMeetingRequest(lead_id="lead_002"))
    print(
        f"  POST /meetings/create -> meeting_link={create_result.meeting_link} "
        f"email_sent={create_result.email_sent} whatsapp_sent={create_result.whatsapp_sent}"
    )
    assert create_result.meeting_link, "POST /meetings/create returned no meeting_link"
    assert create_result.email_sent is True

    emails_after = await list_emails()
    meetings_after = await list_meetings()
    assert len(emails_after) > len(emails_before), "GET /emails did not reflect the email just sent"
    assert len(meetings_after) > len(meetings_before), "GET /meetings did not reflect the meeting just created"

    # webhook.py receives a raw FastAPI Request rather than a typed body
    # model, so it gets a genuine in-process HTTP roundtrip via TestClient
    # instead of a direct function call, exercising the actual ASGI path.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes.webhook import router as webhook_router

    test_app = FastAPI()
    test_app.include_router(webhook_router, prefix="/webhook")
    client = TestClient(test_app)

    webhook_contact = crud.get_primary_contact("lead_001")
    webhook_subject = "Webhook Roundtrip Test - AlphaLogistics"
    await EmailSender().send(
        to_email=webhook_contact["email"],
        subject=webhook_subject,
        body="Testing the inbound webhook path end to end.",
        lead_id="lead_001",
        contact_id=webhook_contact["id"],
    )
    response = client.post(
        "/webhook/email-reply",
        json={
            "data": {
                "from": webhook_contact["email"],
                "subject": f"Re: {webhook_subject}",
                "text": "Sounds great, let's talk.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    print(f"  POST /webhook/email-reply -> status={response.status_code} body={response.json()}")
    assert response.status_code == 200, f"webhook returned {response.status_code}, spec requires it to always return 200"
    assert response.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# Step 8 — Demo Seed Data
# ---------------------------------------------------------------------------
async def test_seed_data() -> None:
    replies = json.loads((SEEDS_DIR / "replies_seed.json").read_text())
    meetings = json.loads((SEEDS_DIR / "meetings_seed.json").read_text())

    required_reply_keys = {"lead_id", "from_email", "subject", "body", "expected_classification"}
    for reply in replies:
        assert required_reply_keys.issubset(reply.keys()), f"reply missing required keys: {reply}"
        assert reply["expected_classification"] in VALID_CLASSIFICATIONS, (
            f"invalid expected_classification: {reply['expected_classification']!r}"
        )
        assert crud.get_lead(reply["lead_id"]) is not None, (
            f"replies_seed.json references unknown lead_id {reply['lead_id']!r}"
        )
    print(f"  replies_seed.json: {len(replies)} entries, all schema-valid and lead_id-resolvable")

    required_meeting_keys = {
        "lead_id", "company_name", "contact_name", "contact_role",
        "meeting_link", "scheduled_at", "briefing",
    }
    required_briefing_keys = {"customer_problem", "recommended_service", "key_points", "watch_out_for"}
    for meeting in meetings:
        assert required_meeting_keys.issubset(meeting.keys()), f"meeting missing required keys: {meeting}"
        assert crud.get_lead(meeting["lead_id"]) is not None, (
            f"meetings_seed.json references unknown lead_id {meeting['lead_id']!r}"
        )
        assert required_briefing_keys.issubset(meeting["briefing"].keys()), (
            f"meeting briefing missing required keys: {meeting['briefing']}"
        )
    print(f"  meetings_seed.json: {len(meetings)} entries, all schema-valid")

    # Confirm the seeded meeting is actually in the database (loaded by
    # backend/load_seeds.py) — the seed file is a real source of truth for
    # the running system, not just an inert fixture other tests read.
    all_meetings = crud.get_all_meetings()
    seed_links = {m["meeting_link"] for m in meetings}
    loaded_links = {m["meeting_link"] for m in all_meetings}
    assert seed_links.issubset(loaded_links), "meetings_seed.json entries were not pre-loaded into the running system"
    print(f"  Confirmed: {len(seed_links)} seed meeting(s) present in crud.get_all_meetings() at startup")


# ---------------------------------------------------------------------------
# Test harness — Step 9 is this script itself
# ---------------------------------------------------------------------------
async def run_step(step: int, name: str, coro: Awaitable[None]) -> None:
    print(f"\n--- Step {step}: {name} ---")
    try:
        await coro
        RESULTS.append(StepResult(step, name, True))
    except AssertionError as exc:
        _log.error("Step %s (%s) FAILED: %s", step, name, exc)
        RESULTS.append(StepResult(step, name, False, str(exc)))
    except Exception as exc:  # noqa: BLE001 — never let one step crash the suite
        _log.error("Step %s (%s) FAILED with an unexpected error: %s", step, name, exc)
        RESULTS.append(StepResult(step, name, False, f"{type(exc).__name__}: {exc}"))


def _print_summary() -> bool:
    print("\n" + "=" * 70)
    print("RESULTS - sufiyan_work.md Steps 1-9")
    print("=" * 70)
    all_passed = True
    for r in RESULTS:
        status = "PASS" if r.passed else "FAIL"
        if not r.passed:
            all_passed = False
        line = f"  [{status}] Step {r.step}: {r.name}"
        if r.detail and not r.passed:
            line += f"\n         -> {r.detail}"
        print(line)
    print("=" * 70)
    print("ALL 9 STEPS PASSED." if all_passed else "SOME STEPS FAILED - see [FAIL] lines above.")
    print("=" * 70)
    return all_passed


async def main() -> None:
    _banner()

    await run_step(1, "Email Sender", test_email_sender())
    await run_step(2, "Response Classifier (9 categories)", test_classification())
    await run_step(3, "Follow-Up Scheduler", test_followup_scheduler())
    await run_step(4, "Email Reader / Inbound Webhook Matching", test_email_reader())
    await run_step(5, "Meeting Manager", test_meeting_flow())
    await run_step(6, "WhatsApp Notifier", test_whatsapp_notifier())
    await run_step(7, "API Routes (emails, meetings, webhook)", test_api_routes())
    await run_step(8, "Demo Seed Data", test_seed_data())
    # Step 9 is this script itself — reaching the summary with a
    # try/except-wrapped harness around every prior step is what
    # "verifies all 9 steps" means in practice.
    RESULTS.append(StepResult(9, "End-to-End Test Script", True, "reached final report"))

    all_passed = _print_summary()
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
