# Agent Pipeline — How it works

This is the AI Brain of AgentHack: a LangGraph pipeline that takes a company's
knowledge (PDF or text) and an Ideal Customer Profile (ICP), then autonomously
finds, researches, scores, and writes outreach emails for qualified leads.

Entry point: `backend/agents/orchestrator.py` → `run_pipeline(session_id, raw_input, input_type, icp_raw)`.

## 1. LangGraph node order

The graph is a strictly sequential `StateGraph` (no branching, no loops).
Each node is one agent's `run(state)` function.

| # | Node name | File | What it does |
|---|---|---|---|
| 1 | `rag` | `backend/agents/rag_agent.py` | Loads the company PDF/text, chunks it, embeds and upserts it into a per-session Qdrant collection. Sets `company_collection` and `company_name`. |
| 2 | `icp` | `backend/agents/icp_agent.py` | Calls the LLM (`ICP_STRUCTURING_PROMPT`) to turn the raw ICP form answers into a structured, typed ICP. |
| 3 | `discovery` | `backend/agents/discovery_agent.py` | Builds 3 search queries from the ICP's keywords, searches Tavily (falling back to Serper), deduplicates by URL. |
| 4 | `filter` | `backend/agents/filter_agent.py` | Cheap first pass — calls the LLM (`FILTER_PROMPT`) with just name + snippet per lead to drop obvious non-fits before expensive research. |
| 5 | `research` | `backend/agents/research_agent.py` | For up to `MAX_LEADS_TO_RESEARCH` (default 10) surviving leads: scrapes the website (Playwright), pulls Apollo company data, and searches recent news via Tavily. |
| 6 | `qualification` | `backend/agents/qualification_agent.py` | Queries the RAG retriever for our own services, then calls the LLM (`QUALIFICATION_PROMPT`) to score each lead 0–100. Drops scores below `MIN_QUALIFICATION_SCORE` (default 40) and sorts descending. |
| 7 | `service_match` | `backend/agents/service_matching_agent.py` | Queries RAG for the full service catalogue, calls the LLM (`SERVICE_MATCHING_PROMPT`) to pick the single best service/product to pitch each qualified lead. |
| 8 | `decision_makers` | `backend/agents/decision_maker_agent.py` | Looks up contacts via Hunter.io, calls the LLM (`DECISION_MAKER_PROMPT`) to pick the best person to target first. |
| 9 | `email_writer` | `backend/agents/email_writer_agent.py` | Generates a Cal.com booking link, calls the LLM (`EMAIL_WRITER_PROMPT`) to write the final personalised outreach email. Populates `outreach_queue`. |

```
rag → icp → discovery → filter → research → qualification →
service_match → decision_makers → email_writer
```

## 2. State object (`PipelineState` TypedDict in `orchestrator.py`)

| Key | Type | Set by |
|---|---|---|
| `session_id` | `str` | caller (`run_pipeline`) |
| `raw_input` | `str` | caller — filepath (if `input_type=="pdf"`) or raw text |
| `input_type` | `str` | caller — `"pdf"` or `"text"` |
| `icp_raw` | `dict` | caller — `{location, industry, size, focus}` |
| `company_collection` | `str` | `rag_agent` — Qdrant collection name, `company_{session_id}` |
| `company_name` | `str` | `rag_agent` — best-effort name from the first chunk |
| `icp` | `dict` | `icp_agent` — `{location, industry, size_range, focus, keywords_to_search}` |
| `raw_leads` | `list[dict]` | `discovery_agent` — `{company_name, url, snippet}` |
| `filtered_leads` | `list[dict]` | `filter_agent` — subset of `raw_leads` |
| `researched_leads` | `list[dict]` | `research_agent` — `filtered_leads` items + `{domain, scraped_text, apollo_data, news_snippets}` |
| `qualified_leads` | `list[dict]` | `qualification_agent` (created, filtered by score, sorted desc); then progressively enriched by `service_matching_agent` (`recommended_service`, `pitch_angle`, `why_it_fits`), `decision_maker_agent` (`primary_contact`), and `email_writer_agent` (`subject`, `body`, `booking_link`) |
| `outreach_queue` | `list[dict]` | `email_writer_agent` — final list of leads ready to send, same shape as the fully-enriched `qualified_leads` entries |

Each lead dict accumulates fields as it flows through the pipeline — nothing
is ever dropped, only added to. By the time a lead reaches `outreach_queue`
it carries every field from discovery through to the final email.

## 3. Rule: all prompts live in `backend/config/prompts.py`

Every string sent to the LLM as a prompt is a named constant in
`backend/config/prompts.py` (`ICP_STRUCTURING_PROMPT`, `FILTER_PROMPT`,
`QUALIFICATION_PROMPT`, `SERVICE_MATCHING_PROMPT`, `DECISION_MAKER_PROMPT`,
`EMAIL_WRITER_PROMPT`). No other file may contain an inline prompt string —
agents only call `PROMPT_NAME.format(...)`. This is the single place to tune
prompt wording without touching agent logic.

## 4. Rule: all agents are `async def run(state: dict) -> dict`

Every one of the 9 nodes exports exactly one function: `async def run(state: dict) -> dict`.
LangGraph invokes them via `await node.run(state)`. `backend/agents/llm_utils.py`
holds the one shared, non-node helper (`get_llm()` + `call_llm_json()`) used
by every agent to call the LLM and robustly parse its JSON response — it is not
a pipeline node and is not wired into the graph.

LLM provider: **Google Gemini** (`ChatGoogleGenerativeAI` from
`langchain-google-genai`, model configured via `settings.GEMINI_MODEL`,
default `gemini-3.5-flash-lite`). Embeddings likewise default to Gemini
(`models/text-embedding-004`) when `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set,
falling back to a local HuggingFace model otherwise — see
`backend/rag/embedder.py`.

## 5. Tool caching (Redis)

Scraper and enrichment tools cache to Redis so the same domain/URL is never
called twice within the TTL window — do not call them twice for the same
input inside one pipeline run either; the cache is there so repeated runs
across sessions stay cheap:

| Tool | Cache key | TTL |
|---|---|---|
| `backend/tools/web_scraper.py` (`scrape`) | `scrape:{url}` | 24h |
| `backend/tools/apollo_enrichment.py` (`enrich_company`) | `apollo:{domain}` | 48h |
| `backend/tools/hunter_email.py` (`find_emails`) | `hunter:{domain}` | 48h |

`backend/utils/cache.py`'s `get_cache`/`set_cache` fail closed — if Redis is
unreachable, every call logs a warning and behaves as a cache miss / no-op
rather than raising. Tools therefore keep working (just uncached) even
without Redis running locally.

## 6. Error handling

Every agent node wraps its entire body in `try/except`, logs the failure via
`backend/utils/logger.py` (never `print()`), and returns `state` **unchanged**
on failure — a broken node never crashes the graph, it just passes state
through untouched to the next node. Within loop-based agents (filter,
research, qualification, service_match, decision_makers, email_writer), each
per-lead unit of work is *also* individually wrapped so one bad lead is
skipped and logged rather than aborting the whole batch.

Tool wrappers (`backend/tools/*.py`) follow the same contract one level down:
they catch their own exceptions, log them, and return an empty structure
(`[]` or `{}`) on failure instead of raising — agents can call them without
their own try/except around every tool call.
