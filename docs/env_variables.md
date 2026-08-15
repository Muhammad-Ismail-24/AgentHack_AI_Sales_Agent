# Environment Variables

Copy `.env.example` to `.env` at the repo root and fill these in. Never commit
`.env` (or the bare `env` file — both are gitignored). Adding a key means
adding it to `.env.example` and `backend/config/settings.py` in the same commit.

Every key is optional at boot: the app starts and `/health` answers even with
an empty file. Features degrade individually rather than crashing — except
Firestore, without which every data route fails.

## LLM — Google Gemini

| Key | Required for | Where to get it |
|---|---|---|
| `GEMINI_API_KEY` | all 9 agents, reply classification, follow-up drafting, meeting briefings | aistudio.google.com → Get API key |
| `GOOGLE_API_KEY` | same — the name the Google SDKs use by convention | either key works; `GEMINI_API_KEY` wins when both are set |
| `GEMINI_MODEL` | optional override, defaults to `gemini-3.5-flash` | — |
| `GEMINI_RPM` | requests/minute budget for the shared key — the limiter in `agents/llm_utils.py` holds every LLM call (agents *and* comms) to this rate | free tier allows 15; default 14 for headroom. Raise on a paid tier. |
| `GEMINI_429_RETRIES` | how many times one call waits out a 429 before failing with a clear quota error | default 2 |

Without a Gemini key the comms LLM drops into mock mode (keyword-heuristic
classification) and the agent pipeline cannot run.

## Research and discovery

| Key | Required for | Where to get it |
|---|---|---|
| `TAVILY_API_KEY` | `discovery_agent.py`, `research_agent.py` — primary web search | tavily.com |
| `SERPER_API_KEY` | fallback search when Tavily is rate-limited | serper.dev |

## Contact enrichment

| Key | Required for | Where to get it |
|---|---|---|
| `APOLLO_API_KEY` | `research_agent.py` — company enrichment | apollo.io → Settings → Integrations → API |
| `HUNTER_API_KEY` | `decision_maker_agent.py` — finding decision-maker emails | hunter.io → API |

## Vector store

| Key | Required for | Notes |
|---|---|---|
| `QDRANT_URL` | RAG over the company document | `http://localhost:6333` under docker-compose |
| `QDRANT_API_KEY` | Qdrant Cloud only | leave blank locally |

## Database — Firestore

| Key | Required for | Notes |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT_PATH` | **everything** | Absolute path to the service-account JSON. Firebase console → Project settings → Service accounts → Generate new private key. Keep the file out of the repo — `*serviceAccount*.json` and `firebase-key*.json` are gitignored. |
| `FIREBASE_PROJECT_ID` | optional | Inferred from the service-account file when omitted. |
| `FIRESTORE_EMULATOR_HOST` | local development only | e.g. `localhost:8080`. Set this **instead of** the service-account path to run with no cloud project. Needs Java 11+. |

If none of these is set, the SDK falls back to Application Default
Credentials (`gcloud auth application-default login`). With no credentials at
all, the API starts but every data route returns 503 and the startup log says
so explicitly.

`DATABASE_URL` is still accepted so an old Postgres URL in your file does not
break validation, but nothing reads it — persistence is Firestore.

## Cache / short-term memory

| Key | Required for | Notes |
|---|---|---|
| `REDIS_URL` | live pipeline status, scrape/search caching | `redis://localhost:6379/0`. Optional: without it the backend falls back to an in-process cache, so the status bar still works for a single-process demo. |

## Email — SMTP is the active path

| Key | Required for | Notes |
|---|---|---|
| `SMTP_HOST` | sending outreach and follow-ups | `smtp.gmail.com` |
| `SMTP_PORT` | — | `587` for STARTTLS, `465` for SSL |
| `SMTP_USER` | — | the full Gmail address |
| `SMTP_PASSWORD` | — | a Google **app password**, not the account password (myaccount.google.com → Security → App passwords) |
| `SENDER_EMAIL` | the From address | defaults to `SMTP_USER` when blank |
| `RESEND_API_KEY` | optional alternative sender | only used when SMTP is not configured. Resend's free tier will only deliver to your own verified address, which is why SMTP is preferred. |

With neither configured, `EmailSender` runs in mock mode: it logs the payload,
records the email in Firestore, and reports success — so the demo flows work
end to end without sending real mail.

## Meetings

| Key | Required for | Where to get it |
|---|---|---|
| `CAL_API_KEY` | generating booking links | cal.com → Settings → Developer → API Keys |
| `CALENDAR_BASE_URL` | optional, defaults to `https://cal.com/admin` | — |

## WhatsApp (Twilio) — currently switched off

`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, and
`ADMIN_WHATSAPP_NUMBER` are declared so the keys validate, but WhatsApp
notifications are disabled for now. `whatsapp_notifier.py` logs instead of
sending when these are blank.

## Frontend

| Key | Required for | Notes |
|---|---|---|
| `VITE_API_URL` | the dashboard's backend origin | `http://localhost:8000` locally. Vite only exposes `VITE_`-prefixed vars to the browser. |

## Tuning (optional)

| Key | Default | What it does |
|---|---|---|
| `LOG_LEVEL` | `INFO` | set `DEBUG` when chasing a bug |
| `FOLLOWUP_AFTER_DAYS` | `3` | days of silence before a follow-up is queued |
| `PIPELINE_STATE_TTL_SECONDS` | `7200` | how long a run's Redis state survives |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `150` | RAG chunking |
| `RETRIEVER_TOP_K` | `5` | chunks retrieved per query |
| `MAX_LEADS_TO_RESEARCH` | `10` | caps the expensive deep-research stage |
| `MIN_QUALIFICATION_SCORE` | `40` | below this a lead is dropped |
| `SENDER_COMPANY_NAME` | `NovaTech Solutions` | signs the outreach emails |
