# Conflicts / Merge Checklist — Comms Layer → Wajeeh's Backend

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

`_deps.py` is a try/except: once `backend/config/settings.py`,
`backend/utils/logger.py`, and `backend/db/crud.py` all exist and import
cleanly, every comms module automatically uses the real ones — **no
changes needed to any `comms/*.py` file**. Deleting the shim files is a
cleanup step, not a requirement for correctness; do it once the real
modules are stable, to stop anyone accidentally depending on the fakes.

## 2. CRUD contract — what `backend/db/crud.py` must implement

The shim implements these exact signatures, exercised end-to-end by
`test_comms.py` through Steps 1-5. Wajeeh's real `crud.py` should match
them (or the comms layer needs small call-site updates — better to match).

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
def update_lead_stage(lead_id: str, stage: str) -> dict | None
```

Column names follow `.claude/skills/database-schema.md` (`leads`,
`contacts`, `emails`, `replies`, `meetings`, `followups` tables). Note:
`get_contact_by_email`, `get_meetings_needing_reminder`, and
`mark_meeting_admin_notified` aren't in `.claude/skills/database-schema.md`
as named functions — they're read/update patterns over the existing
columns (`contacts.email`, `meetings.scheduled_at`,
`meetings.admin_notified`), so no schema change is implied, just these
three query functions.

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
- **`backend/api/`** and **`backend/api/routes/`** — created by this
  session (didn't exist) to hold `webhook.py`. Only `__init__.py` files
  and `webhook.py` exist; `emails.py`, `meetings.py`, and
  `api/schemas.py` are still open (Steps 6-7, and schemas.py per
  FOLDER_STRUCTURE.md is Wajeeh's).

### 4a. Borrowed dependencies beyond config/utils/db

Two more dependencies got the same "defensive import + local fallback"
treatment as `comms/_deps.py`, scoped locally inside `meeting_manager.py`
rather than the central shim (they're not settings/logging/DB, so didn't
belong in `_deps.py`):

- **`tools.calendar_tool.generate_booking_link(company_name: str) -> str`**
  — Ismail's `backend/tools/` (per FOLDER_STRUCTURE.md ownership table).
  Doesn't exist yet. `meeting_manager.py` falls back to a slugified fake
  `https://cal.com/admin/<slug>` link. **When this lands, confirm the
  real function signature matches** — if it differs, `meeting_manager.py`
  needs a one-line call-site update (the `try/except ImportError` block
  at the top of the file, not scattered logic).
- **`comms.whatsapp_notifier.WhatsAppNotifier`** — this is Sufiyan's own
  Step 6, just not built yet in this session (numerical order). Same
  pattern: a stub class returns `False` and logs. No merge risk here —
  once Step 6 is built, delete the `try/except` stub block in
  `meeting_manager.py` (or leave it; it'll just always succeed the `try`).

## 5. Merge tasks (small, do these when main.py exists)

- [ ] Register the scheduler in `backend/main.py`:
      `from comms.followup_scheduler import start_scheduler` +
      call `start_scheduler()` on app startup. Now starts **two** jobs
      (follow-up emails every 6h, pre-meeting reminders every 5min — see
      `followup_scheduler.py`). Note: `@app.on_event("startup")` (as named
      in `sufiyan_work.md`) is deprecated in current FastAPI — prefer a
      `lifespan` context manager instead.
- [ ] Register the webhook router in `backend/main.py`:
      `app.include_router(webhook_router, prefix="/webhook")` per Step 7.
- [ ] Fold `backend/comms/requirements-comms.txt` into the root
      `backend/requirements.txt` once it exists.
- [ ] Add the Section 3 env keys to `.env.example` and
      `docs/env_variables.md`.
- [ ] Wire `backend/api/routes/emails.py` and `meetings.py` (Step 7) —
      not built yet.
- [ ] Once `backend/api/schemas.py` exists, consider moving
      `webhook.py`'s inline payload parsing to a proper Pydantic model
      there — it's inline for now since the file doesn't exist and the
      handler must never fail regardless (see the docstring in
      `webhook.py`).

## 6. Ownership note — `backend/api/routes/` (flagging, not blocking)

`FOLDER_STRUCTURE.md`'s ownership table lists `backend/api/routes/` as
Person 3 (Wajeeh)'s folder. `sufiyan_work.md` explicitly grants Sufiyan
"full ownership" of three specific files inside it: `emails.py`,
`meetings.py`, `webhook.py`. This session followed `sufiyan_work.md` as
the more specific, per-person assignment and created `webhook.py` there.
Worth a quick team confirmation that this reading is correct before Step
7 adds the other two files — if not, these three files should move under
Wajeeh's ownership instead.

## 7. Known repo issues found during this pass (not comms-owned, flagging only)

- **`.gitignore` will silently swallow `.env.example`.** The current
  pattern is `.env.*`, which matches `.env.example` too. `.env.example` is
  called out as a submission requirement with no values
  (`FOLDER_STRUCTURE.md:512`). Needs a `!.env.example` negation line added
  after the `.env.*` pattern. Not fixing here since `.gitignore` changes
  are marked "All — agree before changing" in `FOLDER_STRUCTURE.md`.
