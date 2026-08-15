# Backend — Working Rules

FastAPI + Firestore + LangGraph on Google Gemini. Run it with:

```
cd backend && uvicorn main:app --reload --port 8000
```

## Imports

`backend/` is the import root. Import as `from db import crud`, **not**
`from backend.db import crud` — the `backend.`-prefixed style was normalised
away during the three-way merge, and reintroducing it creates a second copy
of every module (two `settings` singletons, two Firestore clients).

## Non-negotiables

- **Every route handler is `async def`.**
- **All database access goes through `db/crud.py`** (sync) or `db/acrud.py`
  (async). No direct Firestore calls anywhere else. Need a new query? Add it
  to `crud.py`, then add the one-line wrapper to `acrud.py`.
- **All LLM prompts live in `config/prompts.py`.** Never inline a prompt.
- **Never `print()`.** Use `from utils.logger import get_logger`.
- **Never read env vars directly.** Use `from config.settings import settings`.
  New key means updating `settings.py`, `.env.example`, and
  `docs/env_variables.md` in the same commit.
- **Routes return Pydantic schemas from `api/schemas.py`**, never raw dicts.

## Sync vs async — why there are two CRUD modules

The Firestore Admin SDK is synchronous and does real network I/O.

- `db/crud.py` is the source of truth. Sync, returns plain dicts. The comms
  layer (APScheduler jobs, which cannot await) and Sufiyan's routers call it
  directly as `crud.x()`.
- `db/acrud.py` wraps each function in `asyncio.to_thread` so FastAPI handlers
  never block the event loop. Same names, same arguments, just `await`.

Business logic changes go in `crud.py`. `acrud.py` is a pass-through — if you
find yourself putting logic there, it belongs one level down.

```python
from db import acrud                       # in a route
leads = await acrud.get_all_leads(session_id)

from comms._deps import crud               # in comms
crud.create_email(lead_id, contact_id, subject, body, "sent")
```

## Firestore specifics

- Collections mirror the old relational layout: `leads`, `contacts`, `emails`,
  `replies`, `meetings`, `followups`, `pipeline_events`, related by
  `lead_id` / `email_id` fields rather than nesting.
- **There are no joins and no cascades.** `crud.delete_lead()` deletes the
  children by hand; anything that "joins" (the inbox, lead detail) does it in
  Python. Follow that pattern rather than adding compound queries — they need
  composite indexes, and the dataset here is small.
- `_where()` does single-field equality only. Everything else filters in
  Python after one indexed lookup.
- Document factories in `db/models.py` write the full key set including the
  `None`s, so a document read back never needs `.get()` guards.
- Timestamps come back tz-aware; `crud._as_dt()` normalises the stragglers
  (seed strings, naive values) before any comparison.

## Error handling

Raise `HTTPException` with a message a person can act on:

```python
raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")
```

- 400 malformed input · 404 missing document · 409 conflicting state
- 422 valid shape, invalid value (unknown stage) · 503 a dependency is down

Never let an exception escape a background task — catch, `log.exception(...)`,
and record the failure in short-term memory.

## Layering

```
routes  →  acrud / memory        (never call agents or comms directly)
agents  →  orchestrator → comms  (agents never import comms themselves)
comms   →  crud
```

`api/orchestrator_bridge.py` wraps every call into `agents/orchestrator.py` in
a try/except, and `main.py` registers each router the same way. Keep that
pattern: one broken module must never stop the app from booting.

## LLM

One Gemini client, in `agents/llm_utils.py`. The comms layer's
`comms/_llm.py` delegates to it — do not add a second provider client. With no
`GEMINI_API_KEY`/`GOOGLE_API_KEY` set, `complete_json()` returns its caller's
`mock_fallback()` so tests and demos still run.
