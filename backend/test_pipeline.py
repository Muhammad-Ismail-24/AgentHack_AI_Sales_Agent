"""Standalone test script for the full agent pipeline.

Run from the repo root:
    python -m backend.test_pipeline

Loads the seed company text, runs a hardcoded ICP through
orchestrator.run_pipeline(), and prints a summary of what came out.
"""

import asyncio
from pathlib import Path

from agents.orchestrator import run_pipeline
from utils.logger import logger

ROOT_DIR = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT_DIR / "data" / "seeds" / "company_sample.txt"

HARDCODED_ICP = {
    "location": "UAE",
    "industry": "logistics",
    "size": "50-500",
    "focus": "WhatsApp automation",
}


def load_seed_company_text() -> str:
    if SEED_FILE.exists():
        return SEED_FILE.read_text(encoding="utf-8")

    logger.warning(f"{SEED_FILE} not found — using a mocked company description")
    return (
        "Swiftlink Automation is a UAE-based B2B SaaS company that builds "
        "WhatsApp automation, warehouse management, and fleet dispatch "
        "software for logistics companies with 50-500 employees across the "
        "GCC region."
    )


async def main():
    print("=" * 70)
    print("AGENT PIPELINE TEST RUN")
    print("=" * 70)

    company_text = load_seed_company_text()
    print(f"\nLoaded company profile ({len(company_text)} chars) from:")
    print(f"  {SEED_FILE if SEED_FILE.exists() else '(mocked — seed file missing)'}")

    print(f"\nHardcoded ICP: {HARDCODED_ICP}")
    print("\nRunning pipeline (session_id='test_001')... this calls Gemini, "
          "Tavily/Serper, Apollo, and Hunter — it will take a while and needs "
          "real API keys in backend/.env for non-empty results.\n")

    final_state = await run_pipeline(
        session_id="test_001",
        raw_input=company_text,
        input_type="text",
        icp_raw=HARDCODED_ICP,
    )

    raw_leads = final_state.get("raw_leads", [])
    filtered_leads = final_state.get("filtered_leads", [])
    qualified_leads = final_state.get("qualified_leads", [])
    outreach_queue = final_state.get("outreach_queue", [])

    print("=" * 70)
    print("PIPELINE RESULTS")
    print("=" * 70)
    print(f"Company name (from RAG):      {final_state.get('company_name')}")
    print(f"Company collection (Qdrant):  {final_state.get('company_collection')}")
    print(f"Structured ICP:               {final_state.get('icp')}")
    print()
    print(f"Raw leads found:              {len(raw_leads)}")
    print(f"Filtered leads (passed):      {len(filtered_leads)}")
    print(f"Qualified leads (score>=40):  {len(qualified_leads)}")
    print(f"Emails generated:             {len(outreach_queue)}")

    print("\n" + "-" * 70)
    print("TOP 3 QUALIFIED LEADS")
    print("-" * 70)
    if not qualified_leads:
        print("(none — expected if GEMINI_API_KEY / search API keys are "
              "placeholders; the pipeline still ran end-to-end without errors)")
    for i, lead in enumerate(qualified_leads[:3], start=1):
        print(f"\n#{i} {lead.get('company_name', '?')}")
        print(f"    Score:              {lead.get('score')}")
        print(f"    Recommended service: {lead.get('recommended_service')}")
        print(f"    Pitch angle:         {lead.get('pitch_angle')}")

    print("\n" + "-" * 70)
    print("EMAIL PREVIEW — TOP LEAD")
    print("-" * 70)
    if outreach_queue:
        top = outreach_queue[0]
        body = top.get("body", "")
        print(f"To:      {top.get('company_name')}")
        print(f"Subject: {top.get('subject')}")
        print(f"Body (first 100 chars): {body[:100]}")
    else:
        print("(no emails generated — outreach_queue is empty)")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
