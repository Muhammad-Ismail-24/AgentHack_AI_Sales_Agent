# Architecture

## The whole system in one picture

```
                         ┌──────────────────────────┐
   company PDF / text ──►│  POST /company/upload    │
                         │  POST /company/text      │
                         └───────────┬──────────────┘
                                     │ session_id minted here
                                     ▼
                         ┌──────────────────────────┐
                         │  RAG Agent               │──► Qdrant
                         │  chunk → embed → store   │    (company knowledge)
                         └───────────┬──────────────┘
                                     ▼
   ICP form ────────────►┌──────────────────────────┐
                         │  POST /icp/define        │──► Redis (session state)
                         └───────────┬──────────────┘
                                     ▼
                         ┌──────────────────────────┐
                         │  POST /pipeline/start    │  background asyncio task
                         └───────────┬──────────────┘
                                     ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  LangGraph orchestrator — 6 agents, all on Gemini               │
   │                                                                 │
   │  Discovery ─► Filter ─► Research ─► Combined Processing         │
   │  (score + match + pick contact + write email, all leads,        │
   │   in ONE batched LLM call — not one call per lead)              │
   │                                                                 │
   │     Tavily/     batched      Apollo +      Hunter (real         │
   │     Serper      LLM call    Playwright     contacts) +          │
   │                                            Cal.com link         │
   └─────────────────────────────┬───────────────────────────────────┘
                               │ outreach_queue
                               ▼
                    ┌──────────────────────┐
                    │  long_term_memory    │──► Firestore
                    │  .remember_leads()   │    (leads, contacts, …)
                    └──────────┬───────────┘
                               ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  comms/ — outbound and inbound                                  │
   │                                                                 │
   │  email_sender ──► SMTP (Gmail)                                  │
   │  webhook ◄────── inbound reply                                  │
   │      └─► response_classifier (Gemini) ─► stage transition       │
   │  meeting_manager ──► Cal.com link ─► meeting + briefing         │
   │  followup_scheduler (APScheduler) ─► 3-day no-reply follow-up   │
   └───────────────────────────┬─────────────────────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  FastAPI read routes │◄── React dashboard
                    │  /leads /inbox …     │    (polls every 3s / 30s)
                    └──────────────────────┘
```

## Layering

```
routes  →  acrud / memory        never call agents or comms directly
agents  →  orchestrator → comms  agents never import comms themselves
comms   →  crud
```

`api/orchestrator_bridge.py` is the only place routes touch the agent layer,
and it wraps every call in a try/except. `main.py` registers each router the
same way. The rule behind both: **one broken module must never stop the app
from booting**, because three people are pushing to this repo at once.

## Why the data layer looks the way it does

Firestore's Admin SDK is synchronous and does real network I/O. Two modules
fall out of that:

- **`db/crud.py`** — synchronous, returns plain dicts, holds all the logic.
  The comms layer runs inside APScheduler jobs that cannot `await`, so it
  calls this directly.
- **`db/acrud.py`** — the same functions wrapped in `asyncio.to_thread`, so
  FastAPI handlers never block the event loop.

`crud.py` also implements the exact function signatures the comms layer was
originally written against, which is why merging that branch required no
changes inside `comms/` at all.

Firestore has no joins and no cascades, so:
- the inbox and lead-detail "joins" are done in Python;
- `crud.delete_lead()` deletes children explicitly;
- compound filtering happens in Python after one indexed equality lookup,
  which avoids needing composite indexes.

That is fine at demo scale and would need revisiting at thousands of leads.

## Memory: two kinds

| | Short-term | Long-term |
|---|---|---|
| Store | Redis | Firestore |
| Holds | live pipeline state, stage, ICP, company text | leads, contacts, emails, replies, meetings, timeline |
| Lifetime | 2 hours (TTL) | permanent |
| Keyed by | `session_id` | document ids |
| If missing | falls back to an in-process dict | app cannot function |

Redis is genuinely optional — a single-process demo works without it. Firestore
is not.

## The pipeline's state object

Passed node to node by LangGraph:

```python
{
  "company_knowledge": {},   # from RAG
  "icp": {},                 # from the ICP agent
  "raw_leads": [],           # Discovery
  "filtered_leads": [],      # Filter
  "researched_leads": [],    # Research
  "qualified_leads": [],     # Qualification (score + explanation)
  "outreach_queue": [],      # Email Writer
}
```

The route layer mirrors the list lengths into `/pipeline/status` so the
dashboard's progress bar can move without reading the database.

## Failure behaviour

The system is built to degrade rather than crash, because a hackathon demo
that half-works beats one that 500s:

| Missing | Result |
|---|---|
| Redis | in-process cache, single-process only |
| Gemini key | comms LLM returns its caller's mock fallback; agents cannot run |
| SMTP + Resend | `EmailSender` mock mode — records the email, reports success |
| Green API (and Twilio, its fallback) | WhatsApp notifier logs instead of sending |
| Tavily | falls back to Serper |
| Playwright browsers | scraping steps degrade, research continues |
| Orchestrator import | `/pipeline/start` returns 503, dashboard still usable |
| **Firestore** | **every data route fails — this one is fatal** |

`/health` reports Firestore reachability so you can tell the fatal case apart
from the survivable ones at a glance.
