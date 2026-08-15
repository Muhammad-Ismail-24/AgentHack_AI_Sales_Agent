"""Finds and picks the best decision-maker contact to target at each qualified lead."""

import json

from agents.llm_utils import call_llm_json
from config.prompts import DECISION_MAKER_PROMPT
from tools import hunter_email
from utils.logger import logger


def _fallback_contact(lead: dict) -> dict:
    domain = lead.get("domain", "")
    return {
        "name": "Hiring/Ops Team",
        "role": "Unknown",
        "email": f"info@{domain}" if domain else "",
    }


async def run(state: dict) -> dict:
    """Read state['qualified_leads']; for each lead, look up contacts via
    Hunter and pick the best one via DECISION_MAKER_PROMPT. Attaches
    primary_contact to each lead. Updates state['qualified_leads'] in place.
    """
    try:
        qualified_leads = state.get("qualified_leads", []) or []

        updated_leads = []
        for lead in qualified_leads:
            try:
                domain = lead.get("domain", "")
                contacts = hunter_email.find_emails(domain)

                if not contacts:
                    lead = {**lead, "primary_contact": _fallback_contact(lead)}
                    updated_leads.append(lead)
                    continue

                available_contacts = [
                    {
                        "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                        "role": c.get("position", ""),
                        "email": c.get("email", ""),
                    }
                    for c in contacts
                ]

                prompt = DECISION_MAKER_PROMPT.format(
                    recommended_service=lead.get("recommended_service", ""),
                    available_contacts=json.dumps(available_contacts),
                )
                result = await call_llm_json(prompt)

                if isinstance(result, dict) and result.get("primary_contact"):
                    lead = {**lead, "primary_contact": result["primary_contact"]}
                else:
                    lead = {**lead, "primary_contact": available_contacts[0]}

                updated_leads.append(lead)
            except Exception as e:
                logger.warning(
                    f"decision_maker_agent: failed for "
                    f"'{lead.get('company_name', '?')}': {e}"
                )
                updated_leads.append({**lead, "primary_contact": _fallback_contact(lead)})

        state["qualified_leads"] = updated_leads
        logger.info(f"decision_maker_agent: assigned contacts for {len(updated_leads)} leads")
        return state
    except Exception as e:
        logger.error(f"decision_maker_agent failed: {e}")
        return state
