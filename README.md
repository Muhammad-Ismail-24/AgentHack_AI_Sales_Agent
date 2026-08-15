# AgentHack — Autonomous AI Sales Agent

An end-to-end autonomous AI sales system. Feed it a PDF (or a paragraph)
describing your company, tell it who you want to sell to, and it takes over:
it searches the web for matching companies, filters out the bad fits,
researches the survivors, scores them 0–100 with an explanation, picks the
right service to pitch, finds the decision maker, writes a personalised email,
sends it, classifies the reply, books the meeting, and follows up if nobody
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
                        comms/ (SMTP, Cal.com, APScheduler)
                                    │
                                    ▼
                        Firestore  ◄──►  FastAPI  ◄──►  React dashboard
                                          Redis (live pipeline state)
```

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 + TypeScript + Tailwind CSS v3 |
| Backend | Python 3.11 + FastAPI |
| Agents | LangGraph (9 agents) |
| LLM | Google Gemini |
| RAG | LangChain + Qdrant |
| Database | Cloud Firestore |
| Short-term memory | Redis (optional) |
| Email | SMTP (Gmail), Resend optional |
| Meetings | Cal.com |

## Prerequisites

- Python 3.11+
- Node 18+
- A Firebase project with Firestore enabled
- Docker (optional, for the full stack)

## Setup

```bash
git clone https://github.com/Muhammad-Ismail-24/AgentHack_AI_Sales_Agent.git
cd AgentHack_AI_Sales_Agent
cp .env.example .env
```

Fill in `.env` — see `docs/env_variables.md` for what each key does and where
to get it. The one that is genuinely required is
**`FIREBASE_SERVICE_ACCOUNT_PATH`**: Firebase console → Project settings →
Service accounts → *Generate new private key*, then point the variable at the
downloaded JSON. Keep that file outside the repo (the common filenames are
gitignored).

Add `GEMINI_API_KEY` to run the agents, and the SMTP keys to send real email.
Everything else degrades gracefully.

### Run it

Backend:

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend && npm install && npm run dev
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 — health at `/health`, API docs at `/docs`

`/health` reports Firestore reachability; if it does not say `"database":"ok"`,
fix that before anything else.

### Or with Docker

```bash
docker-compose up --build
```

Set `FIREBASE_SERVICE_ACCOUNT_PATH_HOST` in `.env` to the host path of your
service-account JSON — compose mounts it read-only into the backend container.

## Loading demo data

```bash
python backend/load_seeds.py
```

Clears Firestore and loads 12 pre-researched leads, their contacts, sent
outreach, planted replies, and a booked meeting with its briefing — enough to
walk the whole dashboard without waiting on a live pipeline run. The
click-by-click walkthrough is in `docs/demo_script.md`.

## Repository layout

Full tree with per-folder ownership: `FOLDER_STRUCTURE.md`.
Conventions: `CLAUDE.md` (root), `backend/CLAUDE.md`, `frontend/CLAUDE.md`.
Endpoints: `.claude/skills/api-contracts.md`.
Data model: `.claude/skills/database-schema.md`.
