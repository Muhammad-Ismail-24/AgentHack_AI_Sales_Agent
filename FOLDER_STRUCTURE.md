# AgentHack — Autonomous AI Sales Agent
## Complete Project Folder Structure

> **Read this before writing a single file.**
> Every file you create must live inside the folder defined here.
> Do not create new top-level folders without team agreement.
> The ownership column tells you who owns each area — respect it to avoid merge conflicts.

---

## Tech Stack (Finalised)

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 + TypeScript |
| Styling | Tailwind CSS v3 |
| Backend | Python 3.11 + FastAPI |
| Agent Orchestration | LangGraph |
| RAG / Embeddings | LangChain + Qdrant (or Chroma locally) |
| Database | Cloud Firestore |
| Short-term Memory | Redis |
| Web Search | Tavily API |
| Web Scraping | Playwright |
| Contact Enrichment | Apollo.io / Hunter.io |
| Email | SMTP (Gmail); Resend optional |
| Meetings | Cal.com API |
| WhatsApp | Twilio WhatsApp API |
| LLM | Google Gemini (gemini-3.5-flash) via langchain-google-genai |
| Follow-up Scheduling | APScheduler |
| Containerisation | Docker + docker-compose |

---

## Full Folder Tree

```
agenthack/                                 ← Root of the GitHub repo
│
│  ── Claude Code config (loaded every session by all 3 teammates) ──
│
├── CLAUDE.md                              # ★ Master instructions for Claude Code
│                                          #   Contains: project description, tech stack,
│                                          #   build commands, file conventions, agent
│                                          #   architecture notes, DO NOTs
│
├── .claude/                               # Claude Code project-level config folder
│   ├── settings.json                      # Permissions + hooks (committed to git)
│   │                                      #   allow: git commands, pip install, npm run
│   │                                      #   deny: Read(.env), Bash(rm -rf *)
│   ├── settings.local.json                # Personal overrides — NOT committed (in .gitignore)
│   └── skills/                            # Project-specific Claude Code skills
│       ├── agent-pipeline.md              # How the LangGraph pipeline works end-to-end
│       ├── database-schema.md             # Full DB schema so Claude doesn't guess column names
│       ├── api-contracts.md               # Every endpoint: method, path, request, response
│       └── demo-mode.md                   # How to run the demo with seed data
│
├── .claudeignore                          # Files Claude Code skips when reading context
│                                          #   Patterns: data/cache/, data/uploads/,
│                                          #   __pycache__/, node_modules/, .venv/,
│                                          #   *.pyc, dist/, .env, *.log, *.lock
│
│  ── Standard project files ──
│
├── .env.example                           # ★ REQUIRED for submission — all keys, no values
├── .gitignore                             # node_modules, .venv, .env, data/cache, dist, etc.
├── README.md                              # Setup guide, architecture diagram, how to run
├── docker-compose.yml                     # Runs backend + frontend + Redis + Qdrant together
│
│
├── backend/                               # ── PERSON 1 + PERSON 2 ──────────────────────────
│   │
│   ├── CLAUDE.md                          # Backend-specific Claude instructions
│   │                                      #   FastAPI patterns used, import conventions,
│   │                                      #   how agents call each other, async rules
│   │
│   ├── main.py                            # FastAPI app entry point — registers all routers
│   ├── requirements.txt                   # All Python dependencies with pinned versions
│   ├── Dockerfile                         # Backend container definition
│   ├── .env                               # Local secrets — NEVER commit
│   │
│   │
│   ├── config/                            # ── SHARED ── Global constants and prompts
│   │   ├── __init__.py
│   │   ├── settings.py                    # Loads all env vars via pydantic BaseSettings
│   │   └── prompts.py                     # ★ ALL LLM prompt templates live here — nowhere else
│   │
│   │
│   ├── agents/                            # ── PERSON 1 ── Core intelligence pipeline
│   │   ├── __init__.py
│   │   ├── orchestrator.py                # LangGraph master graph — wires all agents in order
│   │   ├── rag_agent.py                   # Ingests company PDF → chunks → embeds → stores
│   │   ├── icp_agent.py                   # Converts ICP form input into structured profile
│   │   ├── discovery_agent.py             # Searches web for companies matching ICP
│   │   ├── filter_agent.py                # Cheap filtering — drops bad fits fast (no deep research)
│   │   ├── research_agent.py              # Deep research: site, news, funding, tech stack
│   │   ├── qualification_agent.py         # Scores each lead 0–100% with explanation
│   │   ├── service_matching_agent.py      # Picks best company service per prospect from RAG
│   │   ├── decision_maker_agent.py        # Finds CEO / CTO / relevant contacts per lead
│   │   └── email_writer_agent.py          # Role-specific personalised outreach email
│   │
│   │
│   ├── comms/                             # ── PERSON 2 ── All communication + scheduling
│   │   ├── __init__.py
│   │   ├── email_sender.py                # Sends emails via SMTP (Resend fallback)
│   │   ├── email_reader.py                # Polls inbox, fetches replies
│   │   ├── response_classifier.py         # Classifies reply type (Interested / Objection / etc.)
│   │   ├── followup_scheduler.py          # APScheduler: queues follow-up email after 3 days
│   │   ├── meeting_manager.py             # Generates Cal.com links, stores meeting details
│   │   └── whatsapp_notifier.py           # Sends admin WhatsApp alerts via Twilio
│   │
│   │
│   ├── rag/                               # ── PERSON 1 ── RAG / vector store layer
│   │   ├── __init__.py
│   │   ├── document_loader.py             # Reads PDF (PyMuPDF) or raw text
│   │   ├── chunker.py                     # Splits document into overlapping chunks
│   │   ├── embedder.py                    # Generates embeddings via Gemini
│   │   ├── vector_store.py                # Qdrant client — upsert and query
│   │   └── retriever.py                   # Query interface used by all agents
│   │
│   │
│   ├── memory/                            # ── PERSON 3 ── Memory layer
│   │   ├── __init__.py
│   │   ├── short_term.py                  # Redis — active agent state, current task context
│   │   └── long_term.py                   # DB read/write — leads, emails, meetings, history
│   │
│   │
│   ├── db/                                # ── PERSON 3 ── Firestore access layer
│   │   ├── __init__.py
│   │   ├── firestore.py                   # Client init + collection names
│   │   ├── models.py                      # Document factories + stage/status constants:
│   │   │                                  #   Lead, Contact, Email, Reply, Meeting,
│   │   │                                  #   FollowUp, PipelineEvent
│   │   ├── crud.py                        # All DB operations (sync, returns dicts)
│   │   └── acrud.py                       # Async wrappers for FastAPI handlers
│   │
│   │
│   ├── api/                               # ── PERSON 3 ── FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── schemas.py                     # All Pydantic request + response models
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── company.py                 # POST /company/upload  POST /company/text
│   │       ├── icp.py                     # POST /icp/define
│   │       ├── pipeline.py                # POST /pipeline/start  GET /pipeline/status/{id}
│   │       ├── leads.py                   # GET /leads  GET /leads/{id}  PATCH /leads/{id}
│   │       ├── emails.py                  # GET /emails  POST /emails/send
│   │       ├── meetings.py                # GET /meetings  POST /meetings/create
│   │       └── webhook.py                 # POST /webhook/email-reply  (inbound reply hook)
│   │
│   │
│   ├── tools/                             # ── PERSON 1 ── External API wrappers
│   │   ├── __init__.py
│   │   ├── tavily_search.py               # Web search via Tavily
│   │   ├── serper_search.py               # Fallback search via Serper
│   │   ├── web_scraper.py                 # Playwright — scrape company pages
│   │   ├── apollo_enrichment.py           # Apollo.io — company + contact enrichment
│   │   ├── hunter_email.py                # Hunter.io — find verified email addresses
│   │   └── calendar_tool.py              # Cal.com API — generate booking links
│   │
│   │
│   └── utils/                             # ── SHARED ── Helpers used across all backend code
│       ├── __init__.py
│       ├── logger.py                      # Centralised logging — import this, not print()
│       ├── cache.py                       # Redis cache helpers — avoid re-fetching same URLs
│       ├── pdf_parser.py                  # PyMuPDF — extract raw text from uploaded PDFs
│       └── validators.py                  # Email format checks, input sanitisation
│
│
├── frontend/                              # ── PERSON 3 ──────────────────────────────────────
│   │
│   ├── CLAUDE.md                          # Frontend-specific Claude instructions
│   │                                      #   Component patterns, Tailwind class conventions,
│   │                                      #   state management rules, API call rules
│   │
│   ├── index.html                         # Vite entry HTML
│   ├── vite.config.ts                     # Vite config — proxy /api → backend:8000
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── package.json
│   ├── Dockerfile                         # Frontend container definition
│   ├── .env                               # VITE_ prefixed vars — NEVER commit
│   │
│   └── src/
│       │
│       ├── main.tsx                       # React root mount
│       ├── App.tsx                        # Router setup (React Router v6)
│       │
│       ├── pages/                         # One file per route
│       │   ├── Onboarding.tsx             # Step 1 — upload company PDF or paste text
│       │   ├── ICP.tsx                    # Step 2 — define ICP (location, industry, size)
│       │   ├── Pipeline.tsx               # Main Kanban board — all lead stages
│       │   ├── Leads.tsx                  # Filterable leads table
│       │   ├── LeadDetail.tsx             # Single lead: research, score, email, contacts
│       │   ├── Inbox.tsx                  # Email replies, classification, next actions
│       │   └── Meetings.tsx               # All meetings — upcoming, admin briefings
│       │
│       ├── components/
│       │   │
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx            # Left nav: Pipeline / Leads / Inbox / Meetings
│       │   │   ├── TopBar.tsx             # Page header with pipeline run status
│       │   │   └── PageWrapper.tsx        # Consistent padding + max-width wrapper
│       │   │
│       │   ├── onboarding/
│       │   │   ├── FileUpload.tsx         # Drag-and-drop PDF upload component
│       │   │   ├── TextInput.tsx          # Paste company description textarea
│       │   │   └── ICPForm.tsx            # ICP form (location, industry, size, goal)
│       │   │
│       │   ├── pipeline/
│       │   │   ├── KanbanBoard.tsx        # Full board with all stage columns
│       │   │   ├── KanbanColumn.tsx       # Single stage column
│       │   │   └── LeadCard.tsx           # Draggable card: name, score badge, stage
│       │   │
│       │   ├── leads/
│       │   │   ├── LeadTable.tsx          # Filterable + sortable leads table
│       │   │   ├── LeadDetail.tsx         # Full lead profile panel
│       │   │   ├── ScoreBadge.tsx         # Colour-coded confidence score pill
│       │   │   ├── ResearchSummary.tsx    # Research findings accordion
│       │   │   ├── EmailPreview.tsx       # Generated email with edit + send button
│       │   │   └── ContactCard.tsx        # Decision-maker: name, role, email, LinkedIn
│       │   │
│       │   ├── inbox/
│       │   │   ├── ReplyCard.tsx          # Incoming reply card
│       │   │   ├── ClassificationBadge.tsx # "Interested" / "Objection" / "Not Now" etc.
│       │   │   └── NextActionPanel.tsx    # Suggested next step for each reply
│       │   │
│       │   ├── meetings/
│       │   │   ├── MeetingCard.tsx        # Meeting: company, time, link, status
│       │   │   └── MeetingBriefing.tsx    # Pre-meeting summary for admin
│       │   │
│       │   └── ui/                        # Design system atoms — keep these generic
│       │       ├── Button.tsx
│       │       ├── Badge.tsx
│       │       ├── Modal.tsx
│       │       ├── Spinner.tsx
│       │       ├── Toast.tsx
│       │       ├── ProgressBar.tsx        # Pipeline run progress indicator
│       │       └── EmptyState.tsx         # Consistent empty state with call to action
│       │
│       ├── lib/
│       │   ├── api.ts                     # ★ ALL backend fetch calls go here — not in components
│       │   ├── types.ts                   # ★ ALL TypeScript interfaces — one source of truth
│       │   │                              #   Lead, Contact, Email, Meeting, ICP, PipelineStage
│       │   └── utils.ts                   # Date formatting, score → colour, text helpers
│       │
│       └── hooks/                         # Custom React hooks
│           ├── usePipeline.ts             # Poll pipeline run status every 3s
│           ├── useLeads.ts                # Fetch + filter leads list
│           └── useInbox.ts                # Fetch replies, auto-refresh every 30s
│
│
├── data/                                  # ── LOCAL ONLY — entire folder in .gitignore ──────
│   ├── uploads/                           # Temp storage for uploaded company PDFs
│   ├── cache/                             # Cached API/scrape responses (saves money on reruns)
│   └── seeds/                             # ★ Demo seed data — coordinate before recording
│       ├── company_sample.pdf             # The demo company's PDF
│       ├── company_sample.txt             # Same company as plain text fallback
│       ├── icp_seed.json                  # Pre-defined ICP for the demo
│       ├── leads_seed.json                # 10–15 pre-researched leads with scores + research
│       ├── emails_seed.json               # Pre-generated outreach emails per lead
│       ├── replies_seed.json              # Planted replies for response classification demo
│       └── meetings_seed.json             # Pre-booked meeting for the meeting flow demo
│
│
└── docs/                                  # ── SHARED ── Team documentation ─────────────────
    ├── architecture.md                    # System design + full agent flow diagram
    ├── api_reference.md                   # Every endpoint: method, path, body, response
    ├── env_variables.md                   # What each .env key does + where to get it
    ├── database_schema.md                 # All tables, columns, types, relationships
    └── demo_script.md                     # Exact click-by-click steps for the demo video
```

---

## Claude Code File Guide

### `CLAUDE.md` (root)
Loaded automatically at the start of every Claude Code session for every teammate.
Put things here that are true for the whole project, every session.

```markdown
# AgentHack — Autonomous AI Sales Agent

## What this is
An end-to-end autonomous AI sales system. It ingests a company PDF,
finds qualified leads, researches them, sends personalised emails,
classifies replies, schedules meetings, and follows up automatically.

## Tech stack
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS
- Backend: Python 3.11 + FastAPI
- Agents: LangGraph
- RAG: LangChain + Qdrant
- DB: Cloud Firestore
- Cache/memory: Redis
- LLM: gemini-3.5-flash (langchain-google-genai)

## Key commands
# Backend
cd backend && uvicorn main:app --reload --port 8000
pip install -r requirements.txt

# Frontend
cd frontend && npm install && npm run dev

# Full stack
docker-compose up --build

## Architecture rules
- ALL LLM prompt templates → backend/config/prompts.py only
- ALL TypeScript types → frontend/src/lib/types.ts only
- ALL frontend API calls → frontend/src/lib/api.ts only
- ALL DB access → backend/db/crud.py (sync) or backend/db/acrud.py (async) only
- Agents must never import from comms/ directly — go through the orchestrator

## DO NOTs
- Never commit .env files
- Never hardcode API keys
- Never add new top-level folders without team agreement
- Never use print() in backend — use utils/logger.py
- Never fetch from components directly — use lib/api.ts
```

---

### `.claude/settings.json`
Controls what Claude Code can do without asking for confirmation.

```json
{
  "permissions": {
    "allow": [
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git status)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git branch *)",
      "Bash(pip install *)",
      "Bash(npm install *)",
      "Bash(npm run dev)",
      "Bash(npm run build)",
      "Bash(uvicorn *)",
      "Bash(python *)",
      "Bash(playwright install *)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Bash(rm -rf *)",
      "Bash(curl * | bash)",
      "Bash(sudo *)"
    ]
  }
}
```

---

### `.claudeignore`
Files Claude Code skips during automatic context loading. Saves tokens.

```
# Dependencies
node_modules/
.venv/
__pycache__/
*.pyc
*.pyo

# Build outputs
dist/
build/
.next/
*.egg-info/

# Secrets — use settings.json deny for hard blocks
.env
.env.*
*.pem
*.key

# Data — large and not useful for coding context
data/uploads/
data/cache/
data/seeds/*.pdf

# Logs and temp files
*.log
*.tmp
.DS_Store

# Lock files (too noisy)
package-lock.json
yarn.lock
poetry.lock
```

---

### `.claude/skills/agent-pipeline.md`
A skill file Claude loads on demand when working on the agent pipeline.

```markdown
# Agent Pipeline — How it works

## LangGraph flow (orchestrator.py)
RAG Agent → ICP Agent → Discovery Agent → Filter Agent →
Research Agent → Qualification Agent → Service Matching Agent →
Decision Maker Agent → Email Writer Agent

## State object passed between nodes
{
  "company_knowledge": {},   # from RAG
  "icp": {},                 # from ICP agent
  "raw_leads": [],           # from Discovery
  "filtered_leads": [],      # after Filter
  "researched_leads": [],    # after Research
  "qualified_leads": [],     # after Qualification (with score + explanation)
  "outreach_queue": []       # after Email Writer
}

## Important: agents are async
All agent functions are async def. Use await for all LLM and tool calls.
```

---

### `.claude/skills/database-schema.md`
A skill file so Claude never guesses column names.

```markdown
# Database Schema

## leads
id, company_name, website, industry, location, employee_count,
pipeline_stage, lead_score, score_explanation, recommended_service,
icp_fit, research_summary, created_at, updated_at

## contacts
id, lead_id (FK), name, role, email, linkedin_url, is_primary

## emails
id, lead_id (FK), contact_id (FK), subject, body, sent_at, status

## replies
id, email_id (FK), raw_body, classification, received_at

## meetings
id, lead_id (FK), contact_id (FK), meeting_link, scheduled_at,
briefing, admin_notified, created_at

## followups
id, lead_id (FK), scheduled_for, status, email_id (FK → sent email)

## pipeline_events
id, lead_id (FK), from_stage, to_stage, reason, created_at
```

---

## Ownership Summary

| Folder / File | Owner | What it contains |
|---|---|---|
| `CLAUDE.md` (root) | All — agree before changing | Master Claude Code instructions |
| `.claude/settings.json` | All — commit changes | Shared permissions + hooks |
| `.claude/skills/` | All — each writes their own | On-demand context for Claude |
| `.claudeignore` | All — agree before changing | What Claude skips |
| `backend/agents/` | Person 1 | All LangGraph agents |
| `backend/rag/` | Person 1 | Vector store, embeddings, retriever |
| `backend/tools/` | Person 1 | Search, scraping, enrichment APIs |
| `backend/config/prompts.py` | Person 1 (others can PR) | All LLM prompts |
| `backend/comms/` | Person 2 | Email, follow-up, meeting, WhatsApp |
| `backend/api/routes/` | Person 3 | All FastAPI endpoints |
| `backend/db/` | Person 3 | Firestore client, document factories, CRUD |
| `backend/memory/` | Person 3 | Short + long term memory |
| `frontend/src/` | Person 3 | All React pages, components, hooks |
| `frontend/src/lib/types.ts` | Person 3 (others can PR) | All TypeScript types |
| `data/seeds/` | All — coordinate before demo | Demo seed data |
| `docs/` | Each writes their own area | Team documentation |

---

## Team Rules (Non-Negotiable)

1. **Never commit `.env`** — only `.env.example` with empty values goes to GitHub
2. **Never commit `data/uploads/` or `data/cache/`** — both are in `.gitignore`
3. **`.claude/settings.local.json`** is personal — goes in `.gitignore`, never pushed
4. **All LLM prompts → `backend/config/prompts.py`** — not scattered in agent files
5. **All TypeScript types → `frontend/src/lib/types.ts`** — one source of truth
6. **All backend API calls from frontend → `frontend/src/lib/api.ts`** — not from components
7. **All DB access → `backend/db/crud.py` / `acrud.py`** — no Firestore calls in routes or agents
8. **Use `backend/utils/logger.py`** — never use `print()` in backend code
9. **Update `docs/env_variables.md`** every time you add a new environment variable
10. **Update `.env.example`** every time you add a new environment variable
11. **Update `.claudeignore`** if you add large generated folders that Claude shouldn't read
12. **`data/seeds/`** is the single source of truth for demo — coordinate before you record

---

## Submission Checklist

- [ ] `.env.example` is in the repo root with all keys and no values
- [ ] `README.md` explains how to install and run the project
- [ ] `docker-compose.yml` spins up the full stack cleanly
- [ ] All three seed files are working and produce a clean demo flow
- [ ] Demo video recorded (max 1.5 min)
- [ ] Code explanation video recorded (max 1 min)
- [ ] GitHub repo is public
