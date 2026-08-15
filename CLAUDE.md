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
- DB: PostgreSQL (Supabase)
- Cache/memory: Redis
- LLM: gemini-3.5-flash-lite (Google Generative AI SDK, via langchain-google-genai)

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
- ALL DB queries → backend/db/crud.py only
- Agents must never import from comms/ directly — go through the orchestrator

## DO NOTs
- Never commit .env files
- Never hardcode API keys
- Never add new top-level folders without team agreement
- Never use print() in backend — use utils/logger.py
- Never fetch from components directly — use lib/api.ts
