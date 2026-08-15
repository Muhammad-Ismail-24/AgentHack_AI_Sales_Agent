# Ismail — Work Breakdown (30%)
## Role: AI Brain & Lead Intelligence

You own everything that makes the system *intelligent* — how the AI reads the company,
finds leads, researches them, scores them, and decides what to sell. This is the core
of the whole product. Without your work nothing else runs.

**Your folders:**
- `backend/rag/` — full ownership
- `backend/agents/` — full ownership (except orchestrator wiring, which you do together with Wajeeh)
- `backend/tools/` — full ownership
- `backend/config/prompts.py` — full ownership
- `backend/utils/` — shared, but you create it first

---

## What You Are Building — Full Description

### 1. RAG Layer (Company Knowledge)
The system must deeply understand the company it is selling for. You build the pipeline
that takes a PDF or raw text of the company, breaks it into chunks, embeds those chunks
into a vector database (Qdrant), and exposes a clean retriever that any agent can call
with a question like "what services does this company offer?" and get a grounded answer.

This is the foundation. Every agent downstream relies on it. If RAG is weak, every email,
every score, every recommendation will be generic and wrong.

### 2. Tool Wrappers (Search, Scrape, Enrich)
You wrap all the external APIs that the agents use to find and research leads:
- **Tavily** — web search to find companies matching the ICP
- **Serper** — fallback search when Tavily fails or rate-limits
- **Playwright** — scrape the actual website of each prospect
- **Apollo.io** — enrich companies with employee count, industry, funding data
- **Hunter.io** — find verified email addresses of decision-makers

Each wrapper must be clean, handle errors gracefully, cache results to Redis
(so the same URL is never scraped twice), and return a standardised dict that agents
can consume without parsing logic inside the agent itself.

### 3. Agent Pipeline (Intelligence Nodes)
You build 8 of the 9 agent nodes that make up the LangGraph pipeline. Each is an
async Python function that takes the shared pipeline state dict and returns an updated
version of it. All prompt templates go into `backend/config/prompts.py` — not inline.

**Agents you own:**
- `rag_agent.py` — triggers ingestion, stores company knowledge, exposes retriever
- `icp_agent.py` — takes the user's ICP form answers, calls Claude to structure them into a typed ICP object
- `discovery_agent.py` — calls Tavily/Serper to find 20–30 candidate companies matching the ICP
- `filter_agent.py` — cheap first pass: calls Claude with just the company name + snippet to discard obvious non-fits without expensive scraping
- `research_agent.py` — for the survivors: scrapes website, pulls Apollo data, news search, builds a full research dict per company
- `qualification_agent.py` — calls Claude with full research + ICP + company knowledge to produce a 0–100 lead score and a plain-English explanation
- `service_matching_agent.py` — calls the RAG retriever + Claude to decide which specific service/product from the company best fits this prospect
- `decision_maker_agent.py` — uses Apollo + Hunter to find the right contacts (CEO, CTO, Head of Sales etc.) and decide which role to target first based on the recommended service
- `email_writer_agent.py` — calls Claude with: prospect research + decision-maker role + recommended service + RAG company knowledge → produces a personalised, evidence-based outreach email

### 4. Config & Prompts
You maintain `backend/config/prompts.py`. Every single string passed to Claude as a
system or user prompt must live here as a named constant. No other file may contain
inline prompt strings. This lets the team tune prompts in one place without touching
agent logic.

---

## Steps for Claude Code to Follow

Work through these steps **in order**. Complete and test each step before moving to the next.
Tell Claude Code to work inside the `backend/` directory throughout.

---

### STEP 1 — Project Bootstrap
**Prompt to give Claude Code:**
```
Set up the Python backend project.
1. Create backend/requirements.txt with these packages:
   fastapi, uvicorn, python-dotenv, pydantic-settings,
   langchain, langchain-anthropic, langgraph,
   qdrant-client, langchain-qdrant,
   pymupdf, playwright,
   tavily-python, requests,
   apscheduler, redis, sqlalchemy,
   alembic, psycopg2-binary, httpx, asyncio
2. Create backend/.env with placeholder values for:
   ANTHROPIC_API_KEY, TAVILY_API_KEY, SERPER_API_KEY,
   APOLLO_API_KEY, HUNTER_API_KEY, QDRANT_URL, QDRANT_API_KEY,
   REDIS_URL, DATABASE_URL
3. Create backend/config/__init__.py (empty)
4. Create backend/config/settings.py that loads all the above
   env vars using pydantic BaseSettings. Every key must have a type annotation.
5. Create backend/config/prompts.py with empty placeholder strings
   for: ICP_STRUCTURING_PROMPT, FILTER_PROMPT, QUALIFICATION_PROMPT,
   SERVICE_MATCHING_PROMPT, DECISION_MAKER_PROMPT, EMAIL_WRITER_PROMPT
6. Create backend/utils/__init__.py, backend/utils/logger.py
   (standard Python logging, INFO level, timestamped format),
   backend/utils/cache.py (Redis get/set helpers with TTL),
   backend/utils/validators.py (email format regex check),
   backend/utils/pdf_parser.py (PyMuPDF extract_text(filepath) function)
Run: pip install -r requirements.txt
```

---

### STEP 2 — RAG Layer
**Prompt to give Claude Code:**
```
Build the RAG layer in backend/rag/.

1. backend/rag/__init__.py (empty)

2. backend/rag/document_loader.py
   - load_from_pdf(filepath: str) -> str  (uses pdf_parser.py)
   - load_from_text(text: str) -> str  (returns as-is after basic clean)

3. backend/rag/chunker.py
   - chunk_text(text: str) -> list[str]
   - Use RecursiveCharacterTextSplitter, chunk_size=800, overlap=150
   - Return list of chunk strings

4. backend/rag/embedder.py
   - get_embeddings() -> Embeddings
   - Return OpenAIEmbeddings or AnthropicEmbeddings (whichever works with Qdrant)
   - Read API key from settings.py

5. backend/rag/vector_store.py
   - QdrantVectorStore class
   - __init__: connect to Qdrant using QDRANT_URL from settings
   - upsert(chunks: list[str], collection: str) -> None
   - collection_exists(collection: str) -> bool

6. backend/rag/retriever.py
   - get_retriever(collection: str) -> VectorStoreRetriever
   - query(question: str, collection: str, k: int = 5) -> str
     (returns joined string of top-k chunk contents)

Test: write a quick test at the bottom of retriever.py under if __name__ == "__main__"
that loads a dummy text, upserts it, then queries it and prints the result.
```

---

### STEP 3 — Tool Wrappers
**Prompt to give Claude Code:**
```
Build all tool wrappers in backend/tools/.

1. backend/tools/__init__.py (empty)

2. backend/tools/tavily_search.py
   - search(query: str, max_results: int = 10) -> list[dict]
   - Each result dict: {title, url, snippet}
   - Use tavily-python client, read key from settings
   - Wrap in try/except, log errors, return [] on failure

3. backend/tools/serper_search.py
   - search(query: str, max_results: int = 10) -> list[dict]
   - Same output shape as Tavily
   - Use requests to call https://google.serper.dev/search
   - Read SERPER_API_KEY from settings

4. backend/tools/web_scraper.py
   - async scrape(url: str) -> str
   - Use Playwright async API
   - Launch chromium headless, goto url, wait 2s, return page text content
   - Strip script/style tags from result
   - Cache result in Redis with 24h TTL (use cache.py helper)
   - Return empty string on failure, log the error

5. backend/tools/apollo_enrichment.py
   - enrich_company(domain: str) -> dict
   - Call Apollo /organizations/enrich endpoint
   - Return: {name, industry, employee_count, location, founded_year, funding_total}
   - Return empty dict on failure

6. backend/tools/hunter_email.py
   - find_emails(domain: str) -> list[dict]
   - Call Hunter domain-search endpoint
   - Return list of: {email, first_name, last_name, position, confidence}

7. backend/tools/calendar_tool.py
   - generate_booking_link(lead_name: str) -> str
   - For now return a Cal.com style URL: https://cal.com/admin/{slug}
   - slug = lead_name lowercased, spaces replaced with hyphens
   - Later: integrate real Cal.com API if time allows

Add a cache.py check at the start of apollo_enrichment and hunter_email too —
if the domain was looked up in the last 48h, return the cached result.
```

---

### STEP 4 — Prompt Templates
**Prompt to give Claude Code:**
```
Fill in backend/config/prompts.py with all prompt templates.
Use Python triple-quoted strings. Use {placeholders} for dynamic values.

Write these prompts:

1. ICP_STRUCTURING_PROMPT
   System: You are a B2B sales strategist. Convert the user's ICP inputs into a structured profile.
   User template: receives target_location, target_industry, company_size, special_focus
   Output: ask Claude to return JSON with keys: location, industry, size_range, focus, keywords_to_search

2. FILTER_PROMPT
   System: You are a fast B2B lead qualifier. Given a company name and a 2-line description,
   decide if it could be a fit for the ICP. Be aggressive at filtering — say NO quickly.
   User template: receives company_name, snippet, icp (JSON string)
   Output: JSON {is_potential_fit: bool, reason: str}

3. QUALIFICATION_PROMPT
   System: You are a senior sales analyst. Score this lead from 0-100 based on ICP fit,
   buying signals, company size, and problem-service fit. Be specific.
   User template: receives company_research (dict), icp (dict), company_knowledge (retrieved RAG text)
   Output: JSON {score: int, explanation: str, top_reasons: list[str], red_flags: list[str]}

4. SERVICE_MATCHING_PROMPT
   System: You are a sales strategist. Based on what you know about the company's services
   and the prospect's situation, pick the single best service to pitch.
   User template: receives company_services (RAG text), prospect_research (dict)
   Output: JSON {recommended_service: str, pitch_angle: str, why_it_fits: str}

5. DECISION_MAKER_PROMPT
   System: You are a B2B sales researcher. Given the service being sold, choose the best
   decision-maker role to target first.
   User template: receives recommended_service, available_contacts (list of {name, role})
   Output: JSON {primary_contact: {name, role, email}, reason: str}

6. EMAIL_WRITER_PROMPT
   System: You are an expert B2B cold email writer. Write a short, personalised, evidence-based
   outreach email. Never invent facts. Max 150 words. No fluff. End with a soft CTA.
   User template: receives contact_name, contact_role, company_name, company_research_summary,
   recommended_service, why_it_fits, booking_link, sender_company_name
   Output: JSON {subject: str, body: str}
```

---

### STEP 5 — Agent Nodes
**Prompt to give Claude Code:**
```
Build all agent nodes in backend/agents/.
Each agent is an async function that receives the shared pipeline state dict and returns
an updated copy of it. Import Claude via: from langchain_anthropic import ChatAnthropic
Use the model name from settings. All prompts come from config/prompts.py — never inline.

1. backend/agents/__init__.py (empty)

2. backend/agents/rag_agent.py
   - async run(state: dict) -> dict
   - Reads state["raw_input"] (either filepath or text string) and state["input_type"] ("pdf" or "text")
   - Loads document, chunks it, upserts into Qdrant collection named "company_{session_id}"
   - Sets state["company_collection"] = collection name
   - Sets state["company_name"] = extracted from first chunk

3. backend/agents/icp_agent.py
   - async run(state: dict) -> dict
   - Reads state["icp_raw"] (dict from form: location, industry, size, focus)
   - Calls Claude with ICP_STRUCTURING_PROMPT
   - Parses JSON response
   - Sets state["icp"] = structured ICP dict

4. backend/agents/discovery_agent.py
   - async run(state: dict) -> dict
   - Reads state["icp"]
   - Builds 3 different search queries from ICP keywords
   - Calls Tavily for each query (falls back to Serper on error)
   - Deduplicates results by URL
   - Sets state["raw_leads"] = list of {company_name, url, snippet}

5. backend/agents/filter_agent.py
   - async run(state: dict) -> dict
   - Reads state["raw_leads"] and state["icp"]
   - For each lead, calls Claude with FILTER_PROMPT (fast, cheap — just name + snippet)
   - Keeps only leads where is_potential_fit == True
   - Sets state["filtered_leads"] = filtered list
   - Logs how many were dropped

6. backend/agents/research_agent.py
   - async run(state: dict) -> dict
   - Reads state["filtered_leads"]
   - For each lead (up to 10 max to save cost):
     * Scrapes website with web_scraper.py
     * Calls apollo_enrichment.py with domain
     * Runs a Tavily news search: "{company_name} funding OR news OR expansion 2024"
   - Builds research dict per lead: {url, scraped_text, apollo_data, news_snippets}
   - Sets state["researched_leads"] = list with research attached

7. backend/agents/qualification_agent.py
   - async run(state: dict) -> dict
   - Reads state["researched_leads"], state["icp"], state["company_collection"]
   - For each lead:
     * Queries RAG retriever: "what services and solutions does our company offer"
     * Calls Claude with QUALIFICATION_PROMPT
     * Parses score + explanation
   - Sorts by score descending
   - Sets state["qualified_leads"] = sorted list, each with score + explanation attached
   - Filters out leads with score < 40

8. backend/agents/service_matching_agent.py
   - async run(state: dict) -> dict
   - Reads state["qualified_leads"], state["company_collection"]
   - For each qualified lead:
     * Queries RAG: "what are all the services, products and packages we offer"
     * Calls Claude with SERVICE_MATCHING_PROMPT
     * Attaches recommended_service + pitch_angle to the lead
   - Sets state["qualified_leads"] = updated list

9. backend/agents/decision_maker_agent.py
   - async run(state: dict) -> dict
   - Reads state["qualified_leads"]
   - For each lead:
     * Calls hunter_email.py with the lead domain to get available contacts
     * Calls Claude with DECISION_MAKER_PROMPT to pick the best one
     * Attaches primary_contact to the lead
   - Sets state["qualified_leads"] = updated list

10. backend/agents/email_writer_agent.py
    - async run(state: dict) -> dict
    - Reads state["qualified_leads"]
    - For each lead:
      * Calls calendar_tool.generate_booking_link(lead company name)
      * Calls Claude with EMAIL_WRITER_PROMPT
      * Attaches {subject, body, booking_link} to the lead
    - Sets state["outreach_queue"] = list of leads ready for sending
    - Sets state["qualified_leads"] = updated list
```

---

### STEP 6 — Orchestrator (do together with Wajeeh)
**Prompt to give Claude Code:**
```
Build backend/agents/orchestrator.py — the LangGraph master graph.

Import all agent run() functions.
Define the pipeline state as a TypedDict with all keys used across agents:
  session_id, raw_input, input_type, icp_raw, company_collection, company_name,
  icp, raw_leads, filtered_leads, researched_leads, qualified_leads, outreach_queue

Build a StateGraph:
  Add nodes: rag, icp, discovery, filter, research, qualification,
             service_match, decision_makers, email_writer
  Add edges in order: rag → icp → discovery → filter → research →
                      qualification → service_match → decision_makers → email_writer
  Set entry point: rag
  Compile the graph

Expose: async run_pipeline(session_id, raw_input, input_type, icp_raw) -> dict
  - Builds initial state
  - Invokes compiled graph
  - Returns final state
```

---

### STEP 7 — Skill File for Your Area
**Prompt to give Claude Code:**
```
Create .claude/skills/agent-pipeline.md at the project root.
Write a detailed markdown file that explains:
1. The full LangGraph node order with one-line description per node
2. The complete state dict with every key, its type, and which agent sets it
3. The rule: all prompts live in backend/config/prompts.py
4. The rule: all agents are async def run(state: dict) -> dict
5. Tool caching: scraper and enrichment tools cache to Redis — do not call twice for same domain
6. Error handling: each agent must catch exceptions, log them, and return state unchanged on failure
```

---

### STEP 8 — Test Your Full Pipeline
**Prompt to give Claude Code:**
```
Create backend/test_pipeline.py — a standalone script to test the full agent pipeline.
1. Load data/seeds/company_sample.txt as the company input
2. Use a hardcoded ICP: {location: "UAE", industry: "logistics", size: "50-500", focus: "WhatsApp automation"}
3. Call orchestrator.run_pipeline() with session_id="test_001"
4. Print the final state: number of raw leads found, filtered leads, qualified leads
5. Print the top 3 qualified leads with their score and recommended service
6. Print the generated email subject + first 100 chars of body for lead #1
Run the script and show the output.
```

---

## What You Hand Off to Wajeeh

When your pipeline is working end-to-end, you give Wajeeh:
- A working `orchestrator.run_pipeline()` function
- The full state dict schema (all keys documented)
- Confirmed output shape of `state["outreach_queue"]` so he can wire it to the email sender

Coordinate with Wajeeh on the state schema **before Step 5** so his comms layer
can consume the right fields without you having to change agent outputs later.

---

## Your Deliverable Checklist

- [ ] `backend/rag/` — all 5 files working, vector store connected
- [ ] `backend/tools/` — all 6 wrappers working with error handling and caching
- [ ] `backend/config/prompts.py` — all 6 prompts written and tested
- [ ] `backend/agents/` — all 9 agent files working
- [ ] `backend/agents/orchestrator.py` — full graph runs end-to-end
- [ ] `backend/utils/` — logger, cache, pdf_parser, validators
- [ ] `backend/test_pipeline.py` — runs cleanly and shows real output
- [ ] `.claude/skills/agent-pipeline.md` — written and committed
- [ ] `docs/architecture.md` — you write the agent flow section
