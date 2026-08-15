# AgentHack — Autonomous AI Sales Agent

An end-to-end autonomous AI sales system. Feed it a PDF (or a paragraph) describing
your company, tell it who you want to sell to, and it takes over from there: it
searches the web for matching companies, filters out the bad fits, researches the
survivors, scores them 0–100 with an explanation, picks the right service to pitch,
finds the decision maker, writes a personalised email, sends it, classifies the
reply, books the meeting, notifies you on WhatsApp, and follows up if nobody
answers.

## Architecture

```
Company PDF / text
        │
        ▼
   RAG Agent ──► Qdrant (company knowledge)
        │
        ▼
   ICP Agent ──► Discovery ──► Filter ──► Research ──► Qualification
                                                            │
                              Email Writer ◄── Decision Maker ◄── Service Match
                                    │
                                    ▼
                            comms/ (Resend, Cal.com, Twilio, APScheduler)
                                    │
                                    ▼
                       PostgreSQL  ◄──►  FastAPI  ◄──►  React dashboard
                                          Redis (live pipeline state)
```

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 + TypeScript + Tailwind CSS v3 |
| Backend | Python 3.11 + FastAPI |
| Agents | LangGraph |
| RAG | LangChain + Qdrant |
| Database | PostgreSQL (Supabase) |
| Short-term memory | Redis |
| LLM | claude-sonnet-4-6 via the Anthropic SDK |

## Prerequisites

- Python 3.11
- Node 18+
- Docker + Docker Compose

## Setup

```bash
git clone https://github.com/Muhammad-Ismail-24/AgentHack_AI_Sales_Agent.git
cd AgentHack_AI_Sales_Agent
cp .env.example .env
```

Fill in the keys in `.env` (see `docs/env_variables.md` for what each one is and
where to get it). At minimum you need `ANTHROPIC_API_KEY`, `DATABASE_URL`,
and `REDIS_URL`.

Then bring up the whole stack:

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (health check at `/health`, docs at `/docs`)

### Running without Docker

Backend:

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend && npm install && npm run dev
```

## Loading demo data

```bash
python backend/load_seeds.py
```

This clears the dev database and loads 12 pre-researched leads, their contacts,
sent outreach emails, planted replies, and a booked meeting — enough to walk the
whole dashboard without waiting on a live pipeline run. The click-by-click demo
walkthrough is in `docs/demo_script.md`.

## Repository layout

The full tree, with per-folder ownership, is documented in `FOLDER_STRUCTURE.md`.
Conventions that apply everywhere are in `CLAUDE.md`.
