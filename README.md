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
| LLM — pipeline & comms | Google Gemini |
| LLM — intelligence layer | Groq |
| RAG | LangChain + Qdrant |
| Database | Cloud Firestore |
| Short-term memory | Redis (optional) |
| Email | SMTP (Gmail), Resend optional |
| Meetings | Cal.com |
| WhatsApp | Green API (Twilio fallback) |
| Text-to-speech | ElevenLabs (optional) |

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

## Intelligence layer

Three extras sit alongside the pipeline rather than inside it, so a normal run
costs exactly what it did before them. All three are human-triggered from the
dashboard — nothing here fires on its own.

**They run on a second LLM provider.** The pipeline and the original comms
features stay on Gemini (`agents/llm_utils.py`); these three run on Groq
(`agents/groq_utils.py`), with its own key, its own rate limiter and its own
model-fallback chain. That split is deliberate: a debate costs three calls,
and on Gemini's free tier — 15 rpm, ~20/day per model — those calls used to
come out of the budget lead processing needed. On separate keys, demoing the
pipeline and demoing the intelligence layer no longer starve each other.

Without `GROQ_API_KEY` all three degrade to **labelled** mock output rather
than failing; the rest of the app is untouched either way.

### Devil's Advocate — `/leads/:id`

A **Prosecutor** agent argues the lead should be dropped, a **Defender**
argues to pursue it, and a **Judge** resolves the argument. The judge's
confidence *is* the lead's confidence score, and the full transcript renders
in the UI, so the reasoning is shown rather than asserted. Every argument on
both sides carries the specific research line it rests on.

The judge is not allowed to overstate its own certainty: `evidence_strength`
is capped in code against how many research fields the lead actually has, so a
debate held over an empty record reads as *low evidence* rather than as
confidence.

### Deal Autopsy Coach — `/leads/:id` (rejected leads only)

When a lead lands in Not Qualified / Not Interested / Do Not Contact, an
autopsy reads the entire thread and issues a three-part post-mortem: the
**cause of death**, the **misfire**, and the **correction**.

The engagement statistics underneath it are computed in Python from the
records — reply latency each way, thread length, days since last touch — not
asked of the model, so *"71h average reply latency against their 4h"* is a
measurement rather than a guess.

Each autopsy also emits a machine-read `misfire_tag`.
`GET /intelligence/autopsies/insights` counts those tags across every autopsy
and maps them to concrete ICP and scoring adjustments. That rollup is the
closed learning loop, and it costs no LLM call to refresh.

An autopsy on a lead that is still live is refused with a 409 — a cause of
death for a deal still in play would be a fabrication.

### Executive Whisperer — `/meetings`

The required T-30min admin reminder, upgraded from a summary into a script:
a verbatim **opening line**, the two objections the prospect will raise each
paired with its rebuttal, the points to land, and the evidence the problem
statement rests on. It is stored on the meeting record, sent over WhatsApp,
and rendered on the meetings page.

**Drive-time audio** renders the same payload as a ~60-second MP3 and sends it
as a WhatsApp voice note, playable from the dashboard. Optional: with no
`ELEVENLABS_API_KEY` the script is still written and still delivered as text,
and the audio endpoint answers 200 with a null URL explaining why.

## Loading demo data

```bash
python backend/load_seeds.py
```

Clears Firestore and loads 12 pre-researched leads, their contacts, sent
outreach, planted replies, and a booked meeting with its briefing — enough to
walk the whole dashboard without waiting on a live pipeline run. The
click-by-click walkthrough is in `docs/demo_script.md`.

## Roadmap

Designed but not built — the vision was larger than the sprint:

| Feature | What it does |
|---|---|
| **The Shadow Cabinet** | Force-directed graph of the buying committee — champion, economic buyer, blocker, ghost — with influence edges inferred from research. |
| **Ghost Radar** | Predicts ghosting 48h ahead from reply-latency decay, message-length shrinkage and sentiment drift, with a one-tap pattern-interrupt rescue. |
| **Trigger Sniper** | Funding/hiring/news event detected → personalised email quoting that trigger, queued for one-tap approval. |
| **Cold Case Reopener** | Every "Not Now" gets a watch condition in long-term memory; the agent reopens itself when the trigger fires months later. |
| **Referral Rebound** | "Wrong person" auto-extracts the named alternative, re-researches them, and re-pitches in one hop. |
| **Counterfactual Rewind** | Re-runs a dead prospect with a different service or persona and shows the score delta — the cure to the autopsy's diagnosis. |
| **Automated Asset Assembler** | Generates a customer-ready PDF one-pager from RAG case studies, attached to the reply. |
| **Meeting Transcriber** | Transcribes an uploaded recording, extracts action items, and auto-creates leads for any new prospect mentioned. |
| **Calibration Scoreboard** | Tracks predicted confidence against actual outcome and renders the calibration curve. |
| **Buyer Twin** | A persona twin built from the research payload that replies to a draft before a real prospect sees it. |

## Repository layout

Full tree with per-folder ownership: `FOLDER_STRUCTURE.md`.
Conventions: `CLAUDE.md` (root), `backend/CLAUDE.md`, `frontend/CLAUDE.md`.
Endpoints: `.claude/skills/api-contracts.md`.
Data model: `.claude/skills/database-schema.md`.
