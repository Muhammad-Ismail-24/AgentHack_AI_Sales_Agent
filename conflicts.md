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

The shim implements these exact signatures. Wajeeh's real `crud.py` should
match them (or the comms layer needs small call-site updates — better to
match).

```python
def create_email(lead_id: str, contact_id: str, subject: str, body: str,
                  status: str, sent_at: datetime | None = None) -> dict
def get_all_emails() -> list[dict]
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

def create_followup(lead_id: str, email_id: str, scheduled_for: datetime,
                     status: str = "sent") -> dict

def get_lead(lead_id: str) -> dict | None
def get_primary_contact(lead_id: str) -> dict | None
def update_lead_stage(lead_id: str, stage: str) -> dict | None
```

Column names follow `.claude/skills/database-schema.md` (`leads`,
`contacts`, `emails`, `replies`, `meetings`, `followups` tables).

**Please coordinate exact signatures before Step 4** (email_reader.py +
webhook.py) — that's where `get_emails_needing_followup` matching logic
("Re: {subject}" matching, from_email → contact matching) gets exercised
for real, per `sufiyan_work.md`.

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

(`CALCOM_API_KEY` isn't consumed yet — that's Step 5's `calendar_tool.py`
— but reserving the name now avoids a naming collision later.)

## 4. Shared files touched by the comms layer

- **`backend/config/prompts.py`** — created by this session, containing
  only `RESPONSE_CLASSIFIER_PROMPT` and `FOLLOWUP_EMAIL_PROMPT`. Ismail's
  agent-pipeline prompts should be added as additional top-level constants
  in the same file (per CLAUDE.md: "ALL LLM prompt templates →
  backend/config/prompts.py only"). Should be a clean additive merge.
- **`data/seeds/replies_seed.json`**, **`data/seeds/meetings_seed.json`** —
  created per the Step 8 spec in `sufiyan_work.md`. `lead_id` values
  (`lead_001`, `lead_002`, `lead_003`) are referenced by the comms shim's
  fake data too — if Wajeeh or Ismail create their own seed leads with
  different IDs, reconcile before the full-pipeline demo.

## 5. Merge tasks (small, do these when main.py exists)

- [ ] Register the follow-up scheduler in `backend/main.py`:
      `from comms.followup_scheduler import start_scheduler` +
      call `start_scheduler()` on app startup. Note: `@app.on_event("startup")`
      (as named in `sufiyan_work.md`) is deprecated in current FastAPI —
      prefer a `lifespan` context manager instead.
- [ ] Fold `backend/comms/requirements-comms.txt` into the root
      `backend/requirements.txt` once it exists.
- [ ] Add the Section 3 env keys to `.env.example` and
      `docs/env_variables.md`.
- [ ] Wire `backend/api/routes/emails.py` (Step 7) to call
      `EmailSender.send()` via `POST /emails/send` — not built yet in this
      session since `backend/api/` doesn't exist.

## 6. Known repo issues found during this pass (not comms-owned, flagging only)

- **`.gitignore` will silently swallow `.env.example`.** The current
  pattern is `.env.*`, which matches `.env.example` too. `.env.example` is
  called out as a submission requirement with no values
  (`FOLDER_STRUCTURE.md:512`). Needs a `!.env.example` negation line added
  after the `.env.*` pattern. Not fixing here since `.gitignore` changes
  are marked "All — agree before changing" in `FOLDER_STRUCTURE.md`.
