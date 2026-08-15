"""Generates the final personalised outreach email for each qualified lead."""

from backend.agents.llm_utils import call_llm_json
from backend.config.prompts import EMAIL_WRITER_PROMPT
from backend.config.settings import settings
from backend.tools.calendar_tool import generate_booking_link
from backend.utils.logger import logger


async def run(state: dict) -> dict:
    """Read state['qualified_leads']; for each lead, generate a Cal.com
    booking link and write a personalised email via EMAIL_WRITER_PROMPT.
    Sets state['outreach_queue'] and updates state['qualified_leads'].
    """
    try:
        qualified_leads = state.get("qualified_leads", []) or []

        outreach_queue = []
        updated_leads = []
        for lead in qualified_leads:
            try:
                company_name = lead.get("company_name", "Prospect")
                contact = lead.get("primary_contact", {}) or {}
                booking_link = generate_booking_link(company_name)

                research_summary = lead.get("explanation") or (
                    lead.get("scraped_text") or ""
                )[:500]

                prompt = EMAIL_WRITER_PROMPT.format(
                    contact_name=contact.get("name", "there"),
                    contact_role=contact.get("role", ""),
                    company_name=company_name,
                    company_research_summary=research_summary,
                    recommended_service=lead.get("recommended_service", ""),
                    why_it_fits=lead.get("why_it_fits", ""),
                    booking_link=booking_link,
                    sender_company_name=settings.SENDER_COMPANY_NAME,
                )
                result = await call_llm_json(prompt)

                email = {
                    "subject": (result or {}).get("subject", f"Quick idea for {company_name}"),
                    "body": (result or {}).get("body", ""),
                    "booking_link": booking_link,
                }

                lead = {**lead, **email}
                updated_leads.append(lead)
                outreach_queue.append(lead)
            except Exception as e:
                logger.warning(
                    f"email_writer_agent: failed for "
                    f"'{lead.get('company_name', '?')}': {e}"
                )
                updated_leads.append(lead)

        state["qualified_leads"] = updated_leads
        state["outreach_queue"] = outreach_queue
        logger.info(f"email_writer_agent: wrote {len(outreach_queue)} emails")
        return state
    except Exception as e:
        logger.error(f"email_writer_agent failed: {e}")
        return state
