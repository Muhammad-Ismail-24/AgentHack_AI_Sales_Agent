"""Scores each researched lead 0-100 against the ICP and our company knowledge."""

import json

from agents.llm_utils import call_llm_json
from config.prompts import QUALIFICATION_PROMPT
from config.settings import settings
from rag.retriever import query as rag_query
from utils.logger import logger


async def run(state: dict) -> dict:
    """Read state['researched_leads'], state['icp'], state['company_collection'];
    for each lead query the RAG retriever, score via QUALIFICATION_PROMPT,
    drop scores below the minimum threshold, sort descending, and set
    state['qualified_leads'].
    """
    try:
        researched_leads = state.get("researched_leads", []) or []
        icp = state.get("icp", {}) or {}
        collection = state.get("company_collection", "")

        company_knowledge = rag_query(
            "what services and solutions does our company offer", collection
        )

        scored_leads = []
        for lead in researched_leads:
            try:
                # Drop the raw scraped text from the JSON blob sent to the LLM —
                # it can be huge; keep the fields the prompt actually needs.
                research_for_prompt = {
                    "company_name": lead.get("company_name"),
                    "url": lead.get("url"),
                    "snippet": lead.get("snippet"),
                    "apollo_data": lead.get("apollo_data"),
                    "news_snippets": lead.get("news_snippets"),
                    "website_excerpt": (lead.get("scraped_text") or "")[:2000],
                }

                prompt = QUALIFICATION_PROMPT.format(
                    company_research=json.dumps(research_for_prompt),
                    icp=json.dumps(icp),
                    company_knowledge=company_knowledge,
                )
                result = await call_llm_json(prompt)
                if not isinstance(result, dict) or "score" not in result:
                    logger.warning(
                        f"qualification_agent: bad result for "
                        f"'{lead.get('company_name', '?')}', skipping"
                    )
                    continue

                score = int(result.get("score", 0))
                scored_leads.append(
                    {
                        **lead,
                        "score": score,
                        "explanation": result.get("explanation", ""),
                        "top_reasons": result.get("top_reasons", []),
                        "red_flags": result.get("red_flags", []),
                    }
                )
            except Exception as e:
                logger.warning(
                    f"qualification_agent: failed to score lead "
                    f"'{lead.get('company_name', '?')}': {e}"
                )

        qualified_leads = [
            lead for lead in scored_leads if lead["score"] >= settings.MIN_QUALIFICATION_SCORE
        ]
        qualified_leads.sort(key=lambda lead: lead["score"], reverse=True)

        state["qualified_leads"] = qualified_leads
        logger.info(
            f"qualification_agent: {len(qualified_leads)}/{len(scored_leads)} leads "
            f"scored >= {settings.MIN_QUALIFICATION_SCORE}"
        )
        return state
    except Exception as e:
        logger.error(f"qualification_agent failed: {e}")
        return state
