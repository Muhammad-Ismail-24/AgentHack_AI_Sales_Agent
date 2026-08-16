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
| `GEMINI_FALLBACK_MODEL` | first model tried when `GEMINI_MODEL` is retired or out of quota | defaults to `gemini-flash-latest` |
| `GEMINI_MODEL_FALLBACKS` | comma-separated models tried after that, each with its own daily budget | defaults to `gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-3.6-flash,gemini-3.7-flash`; blank disables chaining |
| `GEMINI_EMBEDDING_MODEL` | embedding model for the RAG store | defaults to `models/gemini-embedding-001`. `text-embedding-004` is retired and 404s. |
| `GEMINI_RPM` | requests/minute budget for the shared key — the limiter in `agents/llm_utils.py` holds every LLM call (agents *and* comms) to this rate | free tier allows 15; default 14 for headroom. Raise on a paid tier. |
| `GEMINI_429_RETRIES` | how many times the call waits out a 429 *after every model in the chain is spent* | default 2 |

The free tier caps requests **per day, per model** — a 429 names the quota
`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, typically 20/day. Waiting
does not clear that, so `llm_utils` moves along the model chain instead; each
model has its own budget, and `-lite` models are listed first because their
caps are the most generous. Run `GET /v1beta/models` to see which models a key
can actually reach before adding one to the chain.

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
| `RESEND_API_KEY` | alternative sender, over HTTPS | SMTP is tried first, but many managed hosts (Render included) firewall outbound ports 25/465/587, and a send there fails with `[Errno 101] Network is unreachable`. Resend is used automatically when that happens. Its free tier only delivers to your own verified address until you verify a domain. |
| `TEST_RECIPIENT_EMAIL` | redirect all outreach to one inbox | see below. Blank in real use. |

With neither configured, `EmailSender` runs in mock mode: it logs the payload,
records the email in Firestore, and reports success — so the demo flows work
end to end without sending real mail.

### Testing outreach without emailing anyone

`TEST_RECIPIENT_EMAIL` redirects **every** outgoing email — first-touch
outreach, follow-ups and meeting links — to that one address, with a banner
naming who it would have reached. Use it to rehearse the whole loop (send →
reply → classify → book) against your own inbox, and for Resend accounts with
no verified domain, which can only deliver to the account holder.

The subject line is deliberately left untouched: `EmailReader` matches an
inbound reply to its original email by subject, so rewriting it would strand
the reply. Reply normally (keeping `Re: …`) and the reply is matched,
classified, and — if it reads as a meeting request — answered with a booking
link. Leave the variable blank for real outreach.

## Meetings

| Key | Required for | Where to get it |
|---|---|---|
| `CAL_API_KEY` | generating booking links | cal.com → Settings → Developer → API Keys |
| `CALENDAR_BASE_URL` | optional, defaults to `https://cal.com/admin` | — |

## WhatsApp — Green API is the active path

| Key | Required for | Where to get it |
|---|---|---|
| `GREEN_API_URL` | admin + company WhatsApp notifications | defaults to `https://api.greenapi.com`; your instance may use a numbered host like `https://7107.api.greenapi.com` — check the Green API console |
| `GREEN_API_ID_INSTANCE` | — | Green API console → your instance |
| `GREEN_API_TOKEN_INSTANCE` | — | Green API console → your instance. **Treat this like a password — never commit it.** |
| `ADMIN_WHATSAPP_NUMBER` | the 30-minute pre-meeting reminder and meeting-confirmed alert | digits only or `+`-prefixed, e.g. `971501234567` |

Plain REST — no SDK. `whatsapp_notifier.py` POSTs to
`{GREEN_API_URL}/waInstance{GREEN_API_ID_INSTANCE}/sendMessage/{GREEN_API_TOKEN_INSTANCE}`.

**Extra credit — messaging the company directly:** if a lead's contact has a
`phone` field set (see `docs/database_schema.md` → `contacts`), the same
Green API path also sends that contact a short meeting-confirmation message
(no internal briefing content — that stays admin-only) when a meeting is
created. Nothing extra to configure; it activates automatically per-contact.

### Twilio — legacy fallback

`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_FROM` are
declared so the keys validate. `whatsapp_notifier.py` only falls back to
Twilio when Green API isn't configured; with neither configured it logs
instead of sending (mock mode), so the demo still runs with zero credentials.

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
