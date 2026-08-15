"""
Classifies inbound prospect replies via Claude, then decides the next
pipeline action based on the classification.

decide_next_action() returns a plain string decision and does not import
meeting_manager or any other comms module directly — per CLAUDE.md,
"Agents must never import from comms/ directly — go through the
orchestrator." Dispatch on that decision (e.g. calling MeetingManager)
stays with the caller — email_reader.py in Step 4.
"""

from datetime import datetime, timedelta, timezone

from comms._deps import crud, get_logger
from comms._llm import complete_json
from config.prompts import RESPONSE_CLASSIFIER_PROMPT

_log = get_logger("comms.response_classifier")

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


def _mock_classify(reply_body: str) -> dict:
    """Keyword heuristic used only when no ANTHROPIC_API_KEY is configured."""
    text = reply_body.lower()
    if any(w in text for w in ("schedule a call", "book a", "meet", "call this week")):
        classification = "Meeting Requested"
    elif any(w in text for w in ("pricing", "price", "cost", "how much")):
        classification = "Pricing Objection"
    elif any(w in text for w in ("not interested", "no thank")):
        classification = "Not Interested"
    elif any(w in text for w in ("not now", "later", "next quarter")):
        classification = "Not Now"
    elif any(w in text for w in ("wrong person", "not the right", "reach out to")):
        classification = "Wrong Person"
    elif "?" in reply_body:
        classification = "Question"
    else:
        classification = "Interested"
    return {
        "classification": classification,
        "summary": f"(mock) keyword-matched to {classification}",
        "suggested_next_action": "queue_for_review",
    }


class ResponseClassifier:
    async def classify(self, reply_body: str, original_subject: str, company_name: str) -> dict:
        user = RESPONSE_CLASSIFIER_PROMPT["user_template"].format(
            original_email_subject=original_subject,
            company_name=company_name,
            reply_body=reply_body,
        )
        result = await complete_json(
            system=RESPONSE_CLASSIFIER_PROMPT["system"],
            user=user,
            max_tokens=512,
            mock_fallback=lambda: _mock_classify(reply_body),
        )

        classification = result.get("classification")
        if classification not in VALID_CLASSIFICATIONS:
            if classification is not None:
                _log.warning(
                    "Model returned unrecognised classification %r - collapsing to 'Other'",
                    classification,
                )
            classification = "Other"

        return {
            "classification": classification,
            "summary": result.get("summary", ""),
            "suggested_next_action": result.get("suggested_next_action", ""),
        }

    async def decide_next_action(self, classification: str, lead_id: str) -> str:
        if classification == "Interested":
            crud.update_lead_stage(lead_id, "Interested")
            return "stage_updated"

        if classification == "Meeting Requested":
            return "send_meeting_link"

        if classification == "Not Interested":
            crud.update_lead_stage(lead_id, "Not Interested")
            return "stop"

        if classification == "Not Now":
            scheduled_for = datetime.now(timezone.utc) + timedelta(days=14)
            crud.create_followup(lead_id=lead_id, email_id="", scheduled_for=scheduled_for, status="scheduled")
            _log.info("14-day follow-up scheduled for lead_id=%s", lead_id)
            return "followup_scheduled"

        if classification == "Wrong Person":
            return "find_new_contact"

        return "queue_for_review"
