"""Picks the best-fit company service/product to pitch each qualified lead."""

import json

from backend.agents.llm_utils import call_llm_json
from backend.config.prompts import SERVICE_MATCHING_PROMPT
from backend.rag.retriever import query as rag_query
from backend.utils.logger import logger


async def run(state: dict) -> dict:
    """Read state['qualified_leads'], state['company_collection']; for each
    lead query the RAG retriever for our full service catalogue, call the LLM
    with SERVICE_MATCHING_PROMPT, and attach recommended_service/pitch_angle/
    why_it_fits. Updates state['qualified_leads'] in place.
    """
    try:
        qualified_leads = state.get("qualified_leads", []) or []
        collection = state.get("company_collection", "")

        company_services = rag_query(
            "what are all the services, products and packages we offer", collection
        )

        updated_leads = []
        for lead in qualified_leads:
            try:
                prospect_research = {
                    "company_name": lead.get("company_name"),
                    "explanation": lead.get("explanation"),
                    "top_reasons": lead.get("top_reasons"),
                    "apollo_data": lead.get("apollo_data"),
                }
                prompt = SERVICE_MATCHING_PROMPT.format(
                    company_services=company_services,
                    prospect_research=json.dumps(prospect_research),
                )
                result = await call_llm_json(prompt)
                if isinstance(result, dict):
                    lead = {
                        **lead,
                        "recommended_service": result.get("recommended_service", ""),
                        "pitch_angle": result.get("pitch_angle", ""),
                        "why_it_fits": result.get("why_it_fits", ""),
                    }
                updated_leads.append(lead)
            except Exception as e:
                logger.warning(
                    f"service_matching_agent: failed for "
                    f"'{lead.get('company_name', '?')}': {e}"
                )
                updated_leads.append(lead)

        state["qualified_leads"] = updated_leads
        logger.info(f"service_matching_agent: matched services for {len(updated_leads)} leads")
        return state
    except Exception as e:
        logger.error(f"service_matching_agent failed: {e}")
        return state
