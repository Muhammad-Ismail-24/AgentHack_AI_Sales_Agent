# Merge Notes — Wajeeh's Branch

Answers `conflicts.md` from Sufiyan's branch and lists what Ismail needs.
Work through this when `wajeeh-branch` lands on `main`.

---

## For Sufiyan (comms) — 1 line to change

`backend/db/crud.py` is **async and takes an `AsyncSession` first argument**,
because routes, agents, and the memory layer all run on the async engine.
That does not match the sync signatures your shim implements.

Rather than making you rewrite call sites, I added
**`backend/db/sync_crud.py`** — the same functions on a sync session,
returning plain dicts, with **exactly the signatures listed in conflicts.md
section 2**. So the whole merge is one line in `backend/comms/_deps.py`:

```python
from db import sync_crud as crud   # was: from comms import _shim as crud
```

Then delete `backend/comms/_shim.py` and `_deps.py`'s fallback branch.

`sync_crud` implements every function you listed, plus a few you will want for
Step 4:

| Your contract | Status |
|---|---|
| `create_email(lead_id, contact_id, subject, body, status, sent_at=None)` | ✅ exact |
| `get_all_emails()` | ✅ exact |
| `get_emails_needing_followup(days=3)` | ✅ exact — status `sent`, older than cutoff, no reply, no pending/sent follow-up |
| `create_reply(email_id, raw_body, received_at=None)` | ✅ exact, plus optional `classification` / `summary` / `next_action`. Flips the email to `replied` for you. |
| `create_meeting(lead_id, contact_id, meeting_link, status, scheduled_at, briefing)` | ✅ exact |
| `get_all_meetings()` | ✅ exact |
| `create_followup(lead_id, email_id, scheduled_for, status="sent")` | ✅ exact — `email_id` maps to the `original_email_id` column |
| `get_lead(lead_id)` | ✅ exact |
| `get_primary_contact(lead_id)` | ✅ exact — flagged primary first, falls back to the first contact |
| `update_lead_stage(lead_id, stage)` | ✅ exact, `reason` is optional. Writes the `pipeline_events` row automatically. |

Extra, for `email_reader.py` and `webhook.py`:

- `get_contact_by_email(email)` — match an inbound sender to a contact
- `find_email_by_subject(subject, contact_id=None)` — match a thread.
  **Strip the `Re:` / `Fwd:` prefix before calling**; it compares
  case-insensitively against emails in `sent` or `replied`.
- `update_email_status(email_id, status)`
- `update_reply_classification(reply_id, classification, summary, next_action)`

### Your other items

- **Settings keys** — all eight are in `backend/config/settings.py`,
  `.env.example`, and `docs/env_variables.md`, `CALCOM_API_KEY` included.
  Read them via `from config.settings import settings`.
- **`backend/config/prompts.py`** — I did not create it, so your file merges
  clean. Ismail adds his prompts as extra constants in the same file.
- **`requirements-comms.txt`** — already folded into `backend/requirements.txt`
  (`resend`, `twilio`, `APScheduler`). Delete yours on merge.
- **`main.py` scheduler** — done, and using `lifespan` rather than the
  deprecated `@app.on_event("startup")`, as you suggested. It calls
  `comms.followup_scheduler.start_scheduler()` inside a try/except, and
  `stop_scheduler()` on shutdown if it exists. Nothing to do.
- **`.gitignore` swallowing `.env.example`** — fixed, `!.env.example` added.
- **Seed lead ids** — reconciled. `data/seeds/leads_seed.json` uses your exact
  ids, companies, and contact emails: `lead_001` AlphaLogistics /
  ceo@alphalogistics.ae, `lead_002` BetaFreight / ops@betafreight.com,
  `lead_003` GammaSupply / tech@gammasupply.com. `emails_seed.json` uses your
  exact subjects, so your `Re:` subjects match. I copied
  `replies_seed.json` and `meetings_seed.json` from your branch **byte for
  byte** so my loader could be tested against them — they should merge as
  identical files. If you change them, yours wins.

### Still yours to build

`backend/api/routes/emails.py`, `meetings.py`, and `webhook.py`. `main.py`
already tries to register all three by name — drop them in and they appear.
`backend/api/routes/dashboard.py` currently serves read-only `GET /emails` and
`GET /meetings` as stand-ins; it is registered **after** yours, so your
handlers win on the path match the moment they exist. Delete those two
functions from `dashboard.py` once yours land (keep `GET /inbox`, that one is
mine and the frontend depends on it).

---

## For Ismail (agents)

Unblocking files are on this branch: `db/models.py`, `db/crud.py`,
`utils/logger.py`, `utils/cache.py`, plus `config/settings.py`,
`memory/short_term.py`, and `memory/long_term.py`.

**Use the async `db/crud.py`**, not `sync_crud`. Outside a request:

```python
from db.database import session_scope
from memory.long_term import long_term_memory

async with session_scope() as db:
    await long_term_memory.remember_leads(db, state["outreach_queue"], session_id)
```

`upsert_leads_from_pipeline()` dedupes on `company_name` within a `session_id`,
so calling it after each node is safe — leads get updated, not duplicated. It
also accepts a `"contacts"` list on each lead dict and upserts those by email.

### The three functions the API expects from you

`backend/api/orchestrator_bridge.py` wraps `agents.orchestrator` in a
try/except so a missing module cannot stop the app booting. It looks for:

```python
async def ingest_company(*, session_id: str, text: str | None = None,
                          filepath: str | None = None) -> dict
    # -> {"company_name": str, "chars": int, "ingested": True}

async def build_icp(*, session_id: str, raw_icp: dict) -> dict

async def run_pipeline(*, session_id: str, company: dict, icp: dict) -> dict
    # -> the state object; I read "outreach_queue", falling back to
    #    "qualified_leads", and persist whichever is present
```

Keyword arguments, and all three async. Until they exist the routes degrade
gracefully (`POST /pipeline/start` returns 503) rather than 500-ing.

**Report progress** so the dashboard's status bar moves — the frontend polls
every 3 seconds and matches the stage name against this list:

```python
from memory.short_term import short_term_memory
short_term_memory.set_pipeline_stage(session_id, "Researching leads")
```

Stage names the progress bar recognises: `Ingesting company`, `Defining ICP`,
`Discovering leads`, `Filtering leads`, `Researching leads`, `Qualifying leads`,
`Matching services`, `Finding decision makers`, `Writing emails`. Anything else
still displays, it just will not advance the bar.

Also call `short_term_memory.set_pipeline_state(session_id, state)` as the
state grows — the counters on the pipeline page read `raw_leads`,
`filtered_leads`, `qualified_leads`, and `outreach_queue` off it.

---

## Known gaps on this branch

- `POST /emails/send` and `POST /meetings/create` do not exist yet (Sufiyan's).
  The frontend calls them and shows the error in a toast rather than breaking —
  the *Send email* button on a draft will say so until his routes land.
- The pipeline cannot actually run without Ismail's orchestrator. Everything
  else works against seed data.
- `alembic revision --autogenerate` has not been run against a live Postgres.
  The hand-written `0001_initial_schema.py` matches `models.py`; regenerate if
  you change the models.
