"""Deep research on surviving leads: scrape site, Apollo data, and recent news."""

from urllib.parse import urlparse

from config.settings import settings
from tools import apollo_enrichment, tavily_search, web_scraper
from utils.logger import logger


def _domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc or url
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return url


async def run(state: dict) -> dict:
    """Read state['filtered_leads']; for up to MAX_LEADS_TO_RESEARCH leads,
    scrape the website, pull Apollo company data, and search recent news.
    Sets state['researched_leads'] with the research attached to each lead.
    """
    try:
        filtered_leads = state.get("filtered_leads", []) or []
        leads_to_research = filtered_leads[: settings.MAX_LEADS_TO_RESEARCH]

        researched_leads = []
        for lead in leads_to_research:
            try:
                url = lead.get("url", "")
                domain = _domain_from_url(url)
                company_name = lead.get("company_name", domain)

                scraped_text = await web_scraper.scrape(url)
                apollo_data = apollo_enrichment.enrich_company(domain)
                news_snippets = tavily_search.search(
                    f"{company_name} funding OR news OR expansion 2024", max_results=5
                )

                researched_leads.append(
                    {
                        **lead,
                        "domain": domain,
                        "scraped_text": scraped_text,
                        "apollo_data": apollo_data,
                        "news_snippets": news_snippets,
                    }
                )
            except Exception as e:
                logger.warning(
                    f"research_agent: failed to research lead "
                    f"'{lead.get('company_name', '?')}': {e}"
                )

        state["researched_leads"] = researched_leads
        logger.info(f"research_agent: researched {len(researched_leads)} leads")
        return state
    except Exception as e:
        logger.error(f"research_agent failed: {e}")
        return state
