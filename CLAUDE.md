# AgentHack — Autonomous AI Sales Agent

## What this is
An end-to-end autonomous AI sales system. It ingests a company PDF,
finds qualified leads, researches them, sends personalised emails,
classifies replies, schedules meetings, and follows up automatically.

## Tech stack
- Frontend: React 18 + Vite + TypeScript + Tailwind CSS
- Backend: Python 3.11 + FastAPI
- Agents: LangGraph (9 agents)
- RAG: LangChain + Qdrant
- DB: Cloud Firestore
- Cache/memory: Redis (optional — falls back to an in-process cache)
- LLM: gemini-3.5-flash (Google Generative AI SDK, via langchain-google-genai)
- Email: SMTP (Gmail); Resend optional

## Key commands
# Backend
cd backend && uvicorn main:app --reload --port 8000
pip install -r requirements.txt

# Frontend
cd frontend && npm install && npm run dev

# Demo data
python backend/load_seeds.py

# Full stack
docker-compose up --build

## Architecture rules
- ALL LLM prompt templates → backend/config/prompts.py only
- ALL TypeScript types → frontend/src/lib/types.ts only
- ALL frontend API calls → frontend/src/lib/api.ts only
- ALL DB access → backend/db/crud.py (sync) or backend/db/acrud.py (async) only
- Import as `from db import crud`, never `from backend.db import crud` —
  the `backend.` prefix loads every module twice
- One LLM client, in backend/agents/llm_utils.py — comms/_llm.py delegates to it
- Agents must never import from comms/ directly — go through the orchestrator

## DO NOTs
- Never commit .env files (or the bare `env` file — both are gitignored)
- Never commit the Firebase service-account JSON
- Never hardcode API keys
- Never add new top-level folders without team agreement
- Never use print() in backend — use utils/logger.py
- Never fetch from components directly — use lib/api.ts
- Never call Firestore outside db/ — add a function to crud.py instead

## Gotchas that will bite you
- **Firestore has no joins and no cascades.** Anything relational is assembled
  in Python; `crud.delete_lead()` removes children by hand.
- **Dependency pins are load-bearing.** `qdrant-client` pulls a `grpcio-tools`
  that drags in protobuf 7, which silently breaks the Gemini SDK (needs <6).
  Read the pins in backend/requirements.txt before upgrading anything.
- **Gemini models get retired.** A 404 naming the model means it is gone;
  `llm_utils` auto-falls back to `GEMINI_FALLBACK_MODEL`.
- Setup and per-key detail: `docs/env_variables.md`. Merge history and the
  Postgres→Firestore migration: `merge_notes.md`.
