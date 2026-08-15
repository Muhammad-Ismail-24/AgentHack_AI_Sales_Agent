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
| 4 | `filter` | `backend/agents/filter_agent.py` | Cheap first pass — batches leads (`BATCH_FILTER_PROMPT`, `BATCH_SIZE` leads/call) and asks for a same-length JSON array of verdicts, instead of one LLM call per lead. Truncated/malformed responses fall back to `FILTER_PROMPT` per-lead only for the leads the batch didn't cover. |
| 5 | `research` | `backend/agents/research_agent.py` | For up to `MAX_LEADS_TO_RESEARCH` (default 6) surviving leads: scrapes the website (Playwright), pulls Apollo company data, and searches recent news via Tavily. |
| 6 | `combined_processing` | `backend/agents/combined_processing_agent.py` | Scores, service-matches, picks a decision maker, and writes the email for every researched lead **in one batched LLM call** (`BATCH_COMBINED_PROCESSING_PROMPT`, same array-response + per-lead-fallback pattern as `filter`). Decision-maker contacts come from `tools/hunter_email.find_emails()` fetched *before* the prompt is built — the model must pick from that real, per-lead candidate list; a returned contact not in it is discarded in favour of a real one. Drops scores below `MIN_QUALIFICATION_SCORE` (default 40), sorts descending, and populates both `qualified_leads` and `outreach_queue`. |

```
rag → icp → discovery → filter → research → combined_processing
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
| `qualified_leads` | `list[dict]` | `combined_processing_agent` — scored, filtered by `MIN_QUALIFICATION_SCORE`, sorted desc, and fully enriched in the same pass: `score`, `explanation`, `top_reasons`, `red_flags`, `recommended_service`, `pitch_angle`, `why_it_fits`, `primary_contact`, `subject`, `body`, `booking_link` |
| `outreach_queue` | `list[dict]` | `combined_processing_agent` — identical to `qualified_leads` (every qualified lead already has its email written) |

Each lead dict accumulates fields as it flows through the pipeline — nothing
is ever dropped, only added to. By the time a lead reaches `outreach_queue`
it carries every field from discovery through to the final email.

## 3. Rule: all prompts live in `backend/config/prompts.py`

Every string sent to the LLM as a prompt is a named constant in
`backend/config/prompts.py` (`ICP_STRUCTURING_PROMPT`, `FILTER_PROMPT`,
`BATCH_FILTER_PROMPT`, `COMBINED_PROCESSING_PROMPT`,
`BATCH_COMBINED_PROCESSING_PROMPT`). No other file may contain an inline
prompt string — agents only call `PROMPT_NAME.format(...)`. This is the
single place to tune prompt wording without touching agent logic. The
`COMBINED_PROCESSING_PROMPT` / `BATCH_COMBINED_PROCESSING_PROMPT` pair (and
`FILTER_PROMPT` / `BATCH_FILTER_PROMPT`) both follow the same shape: the
batched version is the normal path, the singular version is the per-lead
fallback used only for whatever a truncated batch response didn't cover.

## 4. Rule: all agents are `async def run(state: dict) -> dict`

Every one of the 6 nodes exports exactly one function: `async def run(state: dict) -> dict`.
LangGraph invokes them via `await node.run(state)`. `backend/agents/llm_utils.py`
holds the shared, non-node helpers used by every agent to call the LLM and
robustly parse its JSON response — `get_llm()`, `call_llm_raw()`,
`call_llm_json()`, `extract_json()`, `extract_partial_array()` (truncated
JSON-array recovery, shared by every batching agent), and `is_quota_error()`.
It is not a pipeline node and is not wired into the graph.

LLM provider: **Google Gemini** (`ChatGoogleGenerativeAI` from
`langchain-google-genai`, model configured via `settings.GEMINI_MODEL`,
default `gemini-3.5-flash-lite`). Embeddings likewise default to Gemini
(`models/text-embedding-004`) when `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set,
falling back to a local HuggingFace model otherwise — see
`backend/rag/embedder.py`.

Every Gemini call (agents and comms alike) is throttled by a shared
`TokenBucket` (`backend/utils/rate_limiter.py`, sized by `settings.GEMINI_RPM`)
inside `call_llm_raw()` — continuous refill with burst tolerance, not a hard
sliding-window reset. The same class throttles every other outbound API
integration that can realistically 429 — see the rate-limiting table below.

## 5. Rate limiting and tool caching

Every outbound integration owns its own `TokenBucket` or `SyncTokenBucket`
(`backend/utils/rate_limiter.py`), sized by a `*_RPM` setting, so no single
provider's quota can be exceeded regardless of how many pipeline sessions or
scheduler ticks are running concurrently — one bucket per provider, shared
process-wide:

| Integration | Bucket variant | Setting | Where |
|---|---|---|---|
| Gemini | `TokenBucket` (async) | `GEMINI_RPM` | `agents/llm_utils.py` |
| Green API (WhatsApp) | `TokenBucket` (async) | `GREEN_API_RPM` | `comms/whatsapp_notifier.py` |
| Resend | `TokenBucket` (async) | `RESEND_RPM` | `comms/email_sender.py` |
| Tavily | `SyncTokenBucket` (blocking) | `TAVILY_RPM` | `tools/tavily_search.py` |
| Apollo | `SyncTokenBucket` (blocking) | `APOLLO_RPM` | `tools/apollo_enrichment.py` |
| Hunter | `SyncTokenBucket` (blocking) | `HUNTER_RPM` | `tools/hunter_email.py` |

`SyncTokenBucket` uses `threading.Lock` + `time.sleep`, not `asyncio` — it's
for the plain-`requests`/sync SDK tool modules, which must always be called
via `asyncio.to_thread(...)`, never directly from a coroutine on the event
loop. A throttled wait there would otherwise block the whole server, not
just the caller. `discovery_agent.py` (Tavily), `research_agent.py` (Apollo),
and `combined_processing_agent.py`'s `_prep_lead()` (Hunter) already do this.

Scraper and enrichment tools *also* cache to Redis so the same domain/URL is
never called twice within the TTL window — do not call them twice for the
same input inside one pipeline run either; the cache is there so repeated
runs across sessions stay cheap:

| Tool | Cache key | TTL |
|---|---|---|
| `backend/tools/web_scraper.py` (`scrape`) | `scrape:{url}` | 24h |
| `backend/tools/apollo_enrichment.py` (`enrich_company`) | `apollo:{domain}` | 48h |
| `backend/tools/hunter_email.py` (`find_emails`) | `hunter:{domain}` | 48h |

`backend/utils/cache.py`'s `get_cache`/`set_cache` fail closed — if Redis is
unreachable, every call logs a warning and behaves as a cache miss / no-op
rather than raising. Tools therefore keep working (just uncached) even
without Redis running locally. A cache hit skips the token bucket entirely
(no request means nothing to throttle) — the bucket only guards the actual
network call.

## 6. Error handling

Every agent node wraps its entire body in `try/except`, logs the failure via
`backend/utils/logger.py` (never `print()`), and returns `state` **unchanged**
on failure — a broken node never crashes the graph, it just passes state
through untouched to the next node. Within loop-based agents (research) and
batching agents (filter, combined_processing), each per-lead unit of work is
*also* individually wrapped so one bad lead is skipped and logged rather than
aborting the whole batch or chunk. `filter` and `combined_processing`
additionally stop early and set `state['error']` on a Gemini quota
exhaustion (429) instead of silently returning partial results as if nothing
went wrong.

Tool wrappers (`backend/tools/*.py`) follow the same contract one level down:
they catch their own exceptions, log them, and return an empty structure
(`[]` or `{}`) on failure instead of raising — agents can call them without
their own try/except around every tool call.
