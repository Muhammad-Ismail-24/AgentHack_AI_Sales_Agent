"""
End-to-end smoke test for the comms layer built so far (Steps 1-3).

Run from backend/:
    python test_comms.py

Works with zero API keys configured (everything runs in mock mode) and
gets more meaningful the more real keys you add. See conflicts.md for what
still depends on Wajeeh's backend/db/crud.py landing.
"""

import asyncio
import json
from pathlib import Path

from comms._deps import USING_REAL_BACKEND, crud, get_logger
from comms._llm import is_mock_mode
from comms.email_sender import EmailSender
from comms.followup_scheduler import check_and_send_followups
from comms.response_classifier import ResponseClassifier

_log = get_logger("test_comms")

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"


def _banner() -> None:
    print("=" * 70)
    print("COMMS LAYER SMOKE TEST")
    print(f"  dependency source : {'REAL backend' if USING_REAL_BACKEND else 'shim (comms/_shim.py)'}")
    print(f"  Claude (anthropic): {'MOCK' if is_mock_mode() else 'LIVE'}")
    print(f"  Resend            : {'MOCK' if EmailSender().mock else 'LIVE'}")
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


async def test_meeting_flow() -> None:
    print("\n--- 2. Meeting request flow (simulated - full flow lands in Step 5) ---")
    print("  meeting_manager.py not built yet (depends on calendar_tool.py, Step 5).")
    print("  Seed reference: data/seeds/meetings_seed.json has the expected shape.")


async def test_followup_scheduler() -> None:
    print("\n--- 3. Follow-up scheduler ---")
    candidates_before = crud.get_emails_needing_followup(days=3)
    print(f"  Emails currently qualifying for a 3-day follow-up: {len(candidates_before)}")
    if not candidates_before:
        print("  (expected on a fresh shim run - no emails have been sent yet in this process)")

    sent = await check_and_send_followups()
    print(f"  Follow-ups actually sent this run: {sent}")


async def main() -> None:
    _banner()
    await test_classification()
    await test_meeting_flow()
    await test_followup_scheduler()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
