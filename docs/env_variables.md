# Environment Variables

Copy `.env.example` to `.env` at the repo root and fill these in. Never commit
`.env`. Adding a key here means adding it to `.env.example` and
`backend/config/settings.py` in the same commit.

To just explore the dashboard with seed data, you only need `DATABASE_URL`.
Everything else is required per-feature, and the backend boots without them.

## LLM

| Key | Required for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | every agent, reply classification, email writing | console.anthropic.com → API Keys |
| `LLM_MODEL` | optional override, defaults to `claude-sonnet-4-6` | — |

## Research and discovery

| Key | Required for | Where to get it |
|---|---|---|
| `TAVILY_API_KEY` | discovery + research agents (primary web search) | tavily.com |
| `SERPER_API_KEY` | fallback search when Tavily is rate-limited | serper.dev |

## Contact enrichment

| Key | Required for | Where to get it |
|---|---|---|
| `APOLLO_API_KEY` | decision-maker lookup, company enrichment | apollo.io → Settings → Integrations → API |
| `HUNTER_API_KEY` | verified email discovery | hunter.io → API |

## Vector store

| Key | Required for | Notes |
|---|---|---|
| `QDRANT_URL` | RAG over the company PDF | `http://localhost:6333` under docker-compose |
| `QDRANT_API_KEY` | Qdrant Cloud only | leave blank locally |

## Data stores

| Key | Required for | Notes |
|---|---|---|
| `DATABASE_URL` | everything | `postgresql+asyncpg://admin:password@localhost:5432/agenthack`. Must use the `+asyncpg` driver — Alembic derives the sync URL itself. |
| `REDIS_URL` | live pipeline status, caching | `redis://localhost:6379/0`. Optional: without it the backend falls back to an in-process cache, so the status bar still works for a single-process demo. |

## Email

| Key | Required for | Where to get it |
|---|---|---|
| `RESEND_API_KEY` | sending outreach and follow-ups | resend.com → API Keys |
| `SENDER_EMAIL` | the From address | must be on a domain verified in Resend |

## WhatsApp (Twilio)

| Key | Required for | Notes |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | admin alerts | twilio.com console |
| `TWILIO_AUTH_TOKEN` | admin alerts | twilio.com console |
| `TWILIO_WHATSAPP_FROM` | admin alerts | `whatsapp:+14155238886` on the sandbox |
| `ADMIN_WHATSAPP_NUMBER` | who gets alerted | `whatsapp:+92...` — include the `whatsapp:` prefix |

## Meetings

| Key | Required for | Where to get it |
|---|---|---|
| `CALCOM_API_KEY` | generating booking links | cal.com → Settings → Developer → API Keys |

## Frontend

| Key | Required for | Notes |
|---|---|---|
| `VITE_API_URL` | the dashboard's backend origin | `http://localhost:8000` locally, `http://backend:8000` under docker-compose. Vite only exposes `VITE_`-prefixed vars to the browser. |

## Tuning (optional)

| Key | Default | What it does |
|---|---|---|
| `LOG_LEVEL` | `INFO` | set `DEBUG` when chasing a bug |
| `FOLLOWUP_AFTER_DAYS` | `3` | days of silence before a follow-up is queued |
| `PIPELINE_STATE_TTL_SECONDS` | `7200` | how long a run's Redis state survives |
