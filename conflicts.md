> ## ⚠️ SUPERSEDED — kept for history only
>
> The merge this file plans for has happened. Every item below is done, and
> some of it is now **wrong**: the project's database is Cloud Firestore, not
> PostgreSQL, and the two stand-ins referenced throughout (`comms/_shim.py`,
> `comms/_firestore_crud.py`) have been deleted — `comms/_deps.py` resolves
> straight to the real `db.crud`.
>
> **Read [`merge_notes.md`](merge_notes.md) instead.**

# Conflicts / Merge Checklist — Comms Layer → Wajeeh's Backend

**Status: Sufiyan's section (sufiyan_work.md, all 9 steps) is functionally
complete.** `python backend/test_comms.py` runs all 9 steps with real
assertions and exits 0. See Section 8 for the full deliverable checklist.
What remains is entirely on Wajeeh's and Ismail's side — this file is the
merge guide for when their branches land.

**⚠️ Read Section 9 before assuming this repo's database is Postgres.**
A comms-local Firestore adapter now exists and is active on any machine
with a Firebase service account key configured. It does **not** change
`CLAUDE.md`/`FOLDER_STRUCTURE.md`'s documented architecture (still
Postgres via Supabase) or touch `backend/db/crud.py` (still Wajeeh's,
still doesn't exist) — but the team needs to actually decide whether
Firestore is real or gets dropped. Section 9 has the full writeup.

Sufiyan's comms layer (`backend/comms/`) was built before `backend/config/`,
`backend/utils/`, `backend/db/`, and `backend/main.py` existed. To avoid
blocking, it runs against a local shim (`backend/comms/_shim.py` +
`backend/comms/_deps.py`) that fakes settings, logging, and the DB.

This file tracks everything that needs reconciling once Wajeeh's branch
(DB layer, settings, logger, FastAPI app) lands on `main`. Work through it
top to bottom when that merge happens.

---

## 1. Shim files to delete

- `backend/comms/_shim.py`
- `backend/comms/_deps.py`
- `backend/comms/_firestore_crud.py` — added later (Section 9); same
  "delete once the real backend lands" fate as the other two, **plus** it
  needs a team decision on whether Firestore was ever real to begin with.

`_deps.py` is a try/except: once `backend/config/settings.py`,
`backend/utils/logger.py`, and `backend/db/crud.py` all exist and import
cleanly, every comms module automatically uses the real ones — **no
changes needed to any `comms/*.py` file**. Deleting the shim files is a
cleanup step, not a requirement for correctness; do it once the real
modules are stable, to stop anyone accidentally depending on the fakes.

## 2. CRUD contract — what `backend/db/crud.py` must implement

The shim implements these exact signatures, exercised end-to-end by
`test_comms.py` across all 9 steps, with real assertions (not just
prose output) on every function's behavior. Wajeeh's real `crud.py`
should match them (or the comms layer needs small call-site updates —
better to match).

```python
def create_email(lead_id: str, contact_id: str, subject: str, body: str,
                  status: str, sent_at: datetime | None = None) -> dict
def get_all_emails() -> list[dict]
def get_email(email_id: str) -> dict | None
def update_email_status(email_id: str, status: str) -> dict | None
def get_emails_needing_followup(days: int = 3) -> list[dict]
    # emails where status == "sent", sent_at <= now - days, no reply
    # recorded, and no followup already sent

def create_reply(email_id: str, raw_body: str,
                  received_at: datetime | None = None) -> dict

def create_meeting(lead_id: str, contact_id: str, meeting_link: str,
                    status: str = "link_sent",
                    scheduled_at: datetime | None = None,
                    briefing: dict | None = None) -> dict
def get_all_meetings() -> list[dict]
def get_meeting(meeting_id: str) -> dict | None
def mark_meeting_admin_notified(meeting_id: str) -> dict | None
def get_meetings_needing_reminder(window_minutes: int = 35) -> list[dict]
    # meetings where scheduled_at is within [now, now + window_minutes]
    # and admin_notified is False

def create_followup(lead_id: str, email_id: str, scheduled_for: datetime,
                     status: str = "sent") -> dict

def get_lead(lead_id: str) -> dict | None
def get_primary_contact(lead_id: str) -> dict | None
def get_contact_by_email(email: str) -> dict | None
def get_contact(contact_id: str) -> dict | None
def update_lead_stage(lead_id: str, stage: str) -> dict | None
```

Column names follow `.claude/skills/database-schema.md` (`leads`,
`contacts`, `emails`, `replies`, `meetings`, `followups` tables). Note:
`get_contact_by_email`, `get_contact`, `get_meetings_needing_reminder`,
and `mark_meeting_admin_notified` aren't in
`.claude/skills/database-schema.md` as named functions — they're
read/update patterns over the existing columns (`contacts.id`,
`contacts.email`, `meetings.scheduled_at`, `meetings.admin_notified`), so
no schema change is implied, just these query functions.

`get_contact` (by `contact_id`) was added while building
`api/routes/emails.py` (Step 7) — `POST /emails/send`'s request body
carries `contact_id`, not an email address, so the route needs to resolve
the send-to address itself.

`get_emails_needing_followup` and `get_meetings_needing_reminder`
matching logic ("Re: {subject}" stripping, from_email → contact fallback)
is exercised live in `test_comms.py` section 2 — see that file for the
exact behavior the real `crud.py` needs to support.

## 3. Settings keys needed by comms/

Add these to `backend/config/settings.py` (pydantic `BaseSettings`) and to
`.env.example` / `docs/env_variables.md`:

```
ANTHROPIC_API_KEY=
RESEND_API_KEY=
SENDER_EMAIL=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=
ADMIN_WHATSAPP_NUMBER=
CALCOM_API_KEY=
```

`CALCOM_API_KEY` is not yet consumed — `meeting_manager.py` currently
generates a **mock** booking link (see Section 4a below) because Ismail's
`backend/tools/calendar_tool.py` doesn't exist yet either. Once it lands
and actually calls the Cal.com API, it will be the one reading this key.

**Not part of the above list — deliberately kept separate:**
`FIREBASE_SERVICE_ACCOUNT_PATH` (Section 9). It's for the comms-local
Firestore adapter, not the documented Postgres/Supabase stack, so it does
**not** belong in `config/settings.py`'s `BaseSettings` unless the team
actually adopts Firestore. See Section 9 for what to do with it either way.

## 4. Shared files touched by the comms layer

- **`backend/config/prompts.py`** — contains `RESPONSE_CLASSIFIER_PROMPT`,
  `FOLLOWUP_EMAIL_PROMPT`, and (added while building Step 5)
  `MEETING_BRIEFING_PROMPT`. Ismail's agent-pipeline prompts should be
  added as additional top-level constants in the same file (per
  CLAUDE.md: "ALL LLM prompt templates → backend/config/prompts.py
  only"). Should be a clean additive merge.
- **`data/seeds/replies_seed.json`**, **`data/seeds/meetings_seed.json`** —
  created per the Step 8 spec in `sufiyan_work.md`. `lead_id` values
  (`lead_001`, `lead_002`, `lead_003`) are referenced by the comms shim's
  fake data too — if Wajeeh or Ismail create their own seed leads with
  different IDs, reconcile before the full-pipeline demo.
- **`backend/api/`** and **`backend/api/routes/`** — created to hold
  `webhook.py` (Step 4), and now `emails.py` + `meetings.py` (Step 7).
  All three files owned by Sufiyan per `sufiyan_work.md`. Only
  `__init__.py` files plus these three route files exist — no
  `api/schemas.py` (Wajeeh's, per FOLDER_STRUCTURE.md's file guide, and
  still doesn't exist). See Section 4b below for how the route files
  avoid depending on it.
- **`backend/comms/whatsapp_notifier.py`** — Step 6, built. Message
  templates (including the ✅/⏰ emoji and em dash from
  `sufiyan_work.md`'s spec) are used verbatim. See Section 4a — the
  `meeting_manager.py` stub for this module is now dead code (the real
  import always succeeds) but harmless to leave in place.
- **`docs/api_reference.md`** — created (didn't exist). Contains only the
  Emails / Meetings / Webhook sections (Sufiyan's). Ends with an explicit
  "add your sections below this line" marker for Ismail and Wajeeh —
  same low-conflict pattern as `prompts.py`'s additive-constants approach.

### 4a. Borrowed dependencies beyond config/utils/db

`meeting_manager.py` borrows two dependencies the same "defensive import
+ local fallback" way `comms/_deps.py` borrows Wajeeh's three modules —
scoped locally rather than in the central shim, since neither is
settings/logging/DB:

- **`tools.calendar_tool.generate_booking_link(company_name: str) -> str`**
  — Ismail's `backend/tools/` (per FOLDER_STRUCTURE.md ownership table).
  **Still doesn't exist.** `meeting_manager.py` falls back to a slugified
  fake `https://cal.com/admin/<slug>` link — confirmed working in
  `test_comms.py` (banner reports `tools.calendar_tool: MOCK`). **When
  this lands, confirm the real function signature matches** — if it
  differs, `meeting_manager.py` needs a one-line call-site update (the
  `try/except ImportError` block at the top of the file, not scattered
  logic).
- **`comms.whatsapp_notifier.WhatsAppNotifier`** — **built this session
  (Step 6).** The stub `try/except` block in `meeting_manager.py` now
  always resolves to the real class with zero code changes needed —
  confirmed by `test_comms.py`'s banner flipping from `STUB` to
  `REAL module` with no edits to `meeting_manager.py` itself. The stub
  block can be deleted as cleanup, but there's no urgency — it's dead
  code, not a merge risk.

### 4c. Seed data is now live, not inert (Step 8 completion)

`backend/comms/_shim.py`'s `_ShimCRUD.__init__` now calls a new
`_seed_demo_meeting()` method that reads `data/seeds/meetings_seed.json`
at process startup and loads it directly into `self._meetings` — resolving
each entry's `lead_id` against the shim's fixture leads/contacts,
parsing `scheduled_at` from ISO 8601, and copying `briefing` verbatim.
Best-effort: a missing or malformed seed file logs a warning and leaves
the meeting list empty rather than raising, since this runs at import
time and must never crash the process.

**Why this matters for the merge:** when Wajeeh's real `db/crud.py` and
seed-loading path exist, the equivalent behavior — reading
`data/seeds/*.json` into the real database at demo setup — needs to live
somewhere (a migration, a seed script, or FastAPI startup code). This
shim behavior is the reference implementation for what "seeded" should
mean: `GET /meetings` should show AlphaLogistics's pre-briefed meeting
without any live action being taken first. `replies_seed.json` is
deliberately **not** pre-loaded the same way — it's an input fixture for
testing the classifier/webhook path, not existing state, so loading it
as already-processed replies would be semantically wrong (see how
`test_comms.py` Steps 2 and 8 use it: as raw input to `classify()`, and as
a schema-validation target, never as pre-existing DB rows).

### 4b. Step 7 isolation strategy — why `emails.py` / `meetings.py` don't touch shared files

Per the user's explicit ask, `api/routes/emails.py` and
`api/routes/meetings.py` are self-contained:

- **Local Pydantic schemas** (`EmailSchema`, `SendEmailRequest`,
  `SendEmailResponse` in `emails.py`; `MeetingSchema`,
  `CreateMeetingRequest`, `CreateMeetingResponse` in `meetings.py`)
  instead of importing from a shared `api/schemas.py` — that file doesn't
  exist yet, and defining schemas locally means Wajeeh's own routes/
  schemas can land in the same directory without either of us editing a
  file the other owns. **Merge task once `api/schemas.py` exists:**
  consider moving these up there, but it's optional — nothing breaks if
  they stay local.
- **`backend/api/routes/__init__.py` was not touched** — still an empty
  package marker. No router-aggregation logic was added there, since
  that's exactly the kind of shared file where two people's routers
  would collide on the same lines.
- **Each file only imports from `comms/`** (its own package) — no
  cross-imports between `emails.py` and `meetings.py`, and neither
  imports `webhook.py` or vice versa. Three independent files, each safe
  to review/merge on its own.
- **No router registration happens in these files** — `app.include_router(...)`
  calls belong in `backend/main.py` (Wajeeh's, doesn't exist yet). See
  Section 5's merge tasks for the exact lines needed.

## 5. Merge tasks (small, do these when main.py exists)

- [ ] Register the scheduler in `backend/main.py`:
      `from comms.followup_scheduler import start_scheduler` +
      call `start_scheduler()` on app startup. Now starts **two** jobs
      (follow-up emails every 6h, pre-meeting reminders every 5min — see
      `followup_scheduler.py`). Note: `@app.on_event("startup")` (as named
      in `sufiyan_work.md`) is deprecated in current FastAPI — prefer a
      `lifespan` context manager instead.
- [ ] Register all three routers in `backend/main.py` (all built now —
      Steps 4 and 7):
      ```python
      from api.routes.emails import router as emails_router
      from api.routes.meetings import router as meetings_router
      from api.routes.webhook import router as webhook_router

      app.include_router(emails_router, prefix="/emails")
      app.include_router(meetings_router, prefix="/meetings")
      app.include_router(webhook_router, prefix="/webhook")
      ```
- [ ] Fold `backend/comms/requirements-comms.txt` into the root
      `backend/requirements.txt` once it exists. Now includes `fastapi`
      (needed by the three route files) and `httpx2` (needed only by
      `test_comms.py`'s Step 7 webhook check, via
      `fastapi.testclient.TestClient` — **not** plain `httpx`, which
      current `starlette.testclient` deprecates in favor of `httpx2`),
      alongside `anthropic`, `resend`, `apscheduler`, `twilio`. If
      `httpx2` doesn't make sense as a production dependency, it's fine
      to keep it dev/test-only rather than folding it into the main
      `requirements.txt`.
- [ ] Add the Section 3 env keys to `.env.example` and
      `docs/env_variables.md`.
- [ ] Once `backend/api/schemas.py` exists, consider moving the schemas
      defined locally in `emails.py`/`meetings.py`, and `webhook.py`'s
      inline payload parsing, up there — see Section 4b. Not required;
      the handler in `webhook.py` must never fail regardless, so its
      lenient inline parsing may be intentional even after schemas.py
      exists.

## 6. Ownership note — `backend/api/routes/` (flagging, not blocking)

`FOLDER_STRUCTURE.md`'s ownership table lists `backend/api/routes/` as
Person 3 (Wajeeh)'s folder. `sufiyan_work.md` explicitly grants Sufiyan
"full ownership" of three specific files inside it: `emails.py`,
`meetings.py`, `webhook.py`. This session followed `sufiyan_work.md` as
the more specific, per-person assignment — all three files are now built
(Steps 4 and 7 complete) under that reading. Worth a quick team
confirmation that it's correct; if not, these three files should move
under Wajeeh's ownership instead. Section 4b documents why this shouldn't
cause a merge conflict either way — the files are self-contained and
`routes/__init__.py` was never touched.

## 7. Sufiyan's deliverable checklist — final status

Every item from `sufiyan_work.md`'s checklist, verified by
`backend/test_comms.py`'s 9-step assertion suite (`python
backend/test_comms.py`, exits 0):

- [x] `backend/comms/email_sender.py` — sends via Resend, or logs +
      records in mock mode when `RESEND_API_KEY` is unset. Verified Step 1.
- [x] `backend/comms/response_classifier.py` — classifies all 9
      categories correctly (3 via live/mock classification against seed
      replies, all 9 via direct `decide_next_action()` routing checks).
      Verified Step 2.
- [x] `backend/comms/followup_scheduler.py` — 3-day follow-up logic
      proven with a real positive-path test (a synthetically backdated
      email is detected, followed up, and no longer re-qualifies
      afterward) — not just an always-zero smoke check. Runs via
      APScheduler (`start_scheduler()`), not yet registered in
      `main.py` (doesn't exist — see Section 5). Verified Step 3.
- [x] `backend/comms/email_reader.py` — matches inbound replies by
      subject or contact email, updates email status, classifies, and
      dispatches; also verified to cleanly report `matched: False` for
      an unrecognized sender rather than erroring. Verified Step 4.
- [x] `backend/comms/meeting_manager.py` — generates a link (mock,
      pending Ismail's `calendar_tool.py` — Section 4a), records the
      meeting, emails the prospect, and notifies the admin on WhatsApp;
      `send_pre_meeting_reminder()` also verified to flip
      `admin_notified`. Verified Step 5.
- [x] `backend/comms/whatsapp_notifier.py` — sends meeting-confirmed and
      30-minute pre-meeting briefing messages; confirmed
      `meeting_manager.py` is using the real module, not its Step 6
      stub. Verified Step 6.
- [x] `backend/api/routes/emails.py` — `GET` + `POST` both verified via
      direct calls. Verified Step 7.
- [x] `backend/api/routes/meetings.py` — `GET` + `POST` both verified
      via direct calls. Verified Step 7.
- [x] `backend/api/routes/webhook.py` — inbound reply webhook verified
      via a genuine in-process HTTP roundtrip (FastAPI `TestClient`),
      not just a direct function call. Verified Step 7.
- [x] `data/seeds/replies_seed.json` — 3 replies with correct
      classifications; schema and `lead_id`-resolvability verified.
      Verified Step 8.
- [x] `data/seeds/meetings_seed.json` — 1 complete meeting with
      briefing; schema verified, and confirmed to be actually loaded
      into the running system at startup (Section 4c), not just an
      inert file. Verified Step 8.
- [x] `backend/test_comms.py` — runs clean with visible output; now an
      assertion-based suite (not just prose prints) that catches
      per-step failures, prints a PASS/FAIL summary table, and exits
      non-zero if anything actually failed. This is Step 9 and also
      verifies Steps 1-8.
- [x] `docs/api_reference.md` — created with the Emails, Meetings, and
      Webhook sections.

**What's still open and not fixable from this side:** Ismail's
`backend/tools/calendar_tool.py` (Section 4a — meeting links are mocked
until it lands) and everything in Section 5 (`main.py` doesn't exist yet,
so nothing is registered/running as a live server — every check above
runs by calling the actual functions/ASGI routes directly, not through a
deployed app).

## 8. Known repo issues found during this pass (not comms-owned, flagging only)

- **`.gitignore` will silently swallow `.env.example`.** The current
  pattern is `.env.*`, which matches `.env.example` too. `.env.example` is
  called out as a submission requirement with no values
  (`FOLDER_STRUCTURE.md:512`). Needs a `!.env.example` negation line added
  after the `.env.*` pattern. Not fixing here since `.gitignore` changes
  are marked "All — agree before changing" in `FOLDER_STRUCTURE.md`.

## 9. Comms-local Firestore adapter — NOT the team's database

**Read this whole section before touching `backend/comms/_firestore_crud.py`
or wondering why some machines behave differently from others.**

### What this is and isn't

A Firebase service account key became available locally, and rather than
either ignoring it or unilaterally rewriting `backend/db/crud.py` (which
is Wajeeh's file, not Sufiyan's — see Section 6), the comms layer gained
a **third, optional** backing store: `backend/comms/_firestore_crud.py`,
a Firestore-backed implementation of the exact same CRUD interface the
in-memory shim exposes. It is a drop-in for `comms/_shim.py`'s
`_ShimCRUD`, activated only when `FIREBASE_SERVICE_ACCOUNT_PATH` is set.

**This is explicitly not a decision to adopt Firestore as the project's
database.** `CLAUDE.md` and `FOLDER_STRUCTURE.md` still say Postgres via
Supabase — neither file was edited. `backend/db/crud.py` still doesn't
exist and is still Wajeeh's to build. Nobody without the env var set sees
any behavior change at all — confirmed by running the full 9-step
`test_comms.py` suite both with and without it; both runs pass identically
except for the banner's `dependency source` line.

### How it's wired (`comms/_deps.py`)

Three tiers now, tried in order:

1. **Real backend** (Wajeeh's `config/settings.py` + `utils/logger.py` +
   `db/crud.py`) — once these exist, everything below is dead code, same
   as before.
2. **Comms-local Firestore adapter** — tried only when
   `FIREBASE_SERVICE_ACCOUNT_PATH` is set in the environment. If the
   import or Firestore init fails for any reason (bad path, revoked key,
   `firebase-admin` not installed), it's caught and logged, and execution
   falls through to tier 3 — a broken Firestore config can never break
   the comms layer.
3. **In-memory shim** — the original fallback, unchanged. This is what
   everyone without a Firebase key gets.

### Scope: what's actually in Firestore vs. what's still a fixture

Only the data comms actually owns went to real Firestore collections:
`emails`, `replies`, `meetings`, `followups` — matching the same document
shapes as the CRUD contract in Section 2. **Leads and contacts are NOT in
Firestore** — `_firestore_crud.py` keeps the same local fixture dicts
`_shim.py` uses (3 demo leads/contacts, identical values). Real lead/
contact data ownership isn't a call this adapter tries to make.

The Step 8 demo-meeting seed (Section 4c) was ported here too, with one
difference: it's **idempotent** — Firestore persists across process runs
(unlike the in-memory shim, which starts empty every time), so
`_seed_demo_meeting()` checks for an existing document by `meeting_link`
before writing, instead of duplicating the seed meeting on every run.

### Verified against the real Firestore project

`python backend/test_comms.py` was run with `FIREBASE_SERVICE_ACCOUNT_PATH`
pointed at the real key — all 9 steps passed against actual network calls
(visible in the log timestamps: ~700ms–1s per Firestore round trip, not
the near-instant in-memory shim). Every CRUD function in Section 2's
contract round-tripped through real Firestore, including the ones named
in the original ask: `get_email`, `update_email_status`, `get_meeting`,
`mark_meeting_admin_notified`, `get_meetings_needing_reminder`,
plus all the `create_*`/`get_all_*` functions.

**Practical note:** because Firestore is a real, persistent cloud
resource, every test run against it writes real documents — repeated runs
accumulate `emails`/`replies`/`meetings`/`followups` documents over time
(the demo-meeting seed is the one exception, being idempotent). Not a
concern at hackathon scale, but if the Firestore free-tier quota ever
becomes a factor, clear the collections from the Firebase Console between
demo runs.

### Security — the service account key

`agenthack-dc1a0-firebase-adminsdk-fbsvc-5990f3a823.json` sits at the repo
root. As of this writing it is **not tracked by git and has never
appeared in commit history** — verified via `git ls-files` and
`git log --all -- <filename>` before touching anything. `.gitignore` was
also fixed as part of this change (it had picked up a blanket `*.json`
rule, presumably to hide this file, which would have silently stopped
tracking `data/seeds/*.json` and any other legitimate JSON files going
forward) — replaced with scoped patterns
(`*firebase-adminsdk*.json`, `serviceAccountKey.json`, `*serviceAccount*.json`).

**Rules for anyone using this adapter:**
- **Never commit this file, or any Firebase/GCP service account key.**
  The `.gitignore` patterns above cover common naming conventions, but
  don't rely on that alone — double-check `git status` before committing
  anything near it.
- **Don't share this specific key file** (Slack, email, a shared drive).
  Anyone who wants to use the adapter should generate their **own** key:
  Firebase Console → Project Settings → Service Accounts → Generate new
  private key, for the `agenthack-dc1a0` project.
- **The path is read from `FIREBASE_SERVICE_ACCOUNT_PATH`, never
  hardcoded** — nothing in `comms/_firestore_crud.py` or `comms/_shim.py`
  references the literal filename.
- **If this key is ever exposed** (committed, pasted somewhere public,
  shared insecurely) — rotate/revoke it immediately in the Firebase
  Console and issue a new one. Don't assume it's fine because it was
  caught quickly.

### Team decision needed

This adapter proves Firestore *can* work for the comms-owned tables. It
does not decide whether it *should* — that's a real architecture call
with consequences for Wajeeh's DB layer (Postgres per current docs) and
anything Ismail's RAG/agent layer might eventually need from a relational
store. Options, to be discussed before this goes further:

1. **Adopt Firestore for real.** Update `CLAUDE.md` and
   `FOLDER_STRUCTURE.md`'s stated architecture, and `backend/db/crud.py`
   becomes a Firestore implementation (this file's logic is the starting
   point) instead of a Postgres one.
2. **Drop it.** Keep Postgres/Supabase as documented; treat this adapter
   as a local experiment, and delete `_firestore_crud.py` +
   `FIREBASE_SERVICE_ACCOUNT_PATH` references once Wajeeh's real
   Postgres-backed `crud.py` lands.
3. **Something else** (e.g., Firestore for a subset of tables, Postgres
   for the rest) — needs its own discussion; not something to infer from
   this adapter existing.

Until the team decides, this stays exactly what it is: an opt-in,
comms-local, fully-fallback-safe adapter that changes nothing for anyone
who doesn't set the env var.
