# Backend — Working Rules

FastAPI + SQLAlchemy (async) + LangGraph. Run it with:

```
cd backend && uvicorn main:app --reload --port 8000
```

## Imports

`backend/` is the import root. Import as `from db import crud`, not
`from backend.db import crud`. Never use relative imports across packages.

## Non-negotiables

- **Every route handler is `async def`.** No sync handlers — they block the loop.
- **All DB access goes through `db/crud.py`.** No raw SQL and no `select()` in
  routes, agents, or comms. If you need a new query, add a function to `crud.py`.
- **All LLM prompts live in `config/prompts.py`.** Never inline a prompt string.
- **Never `print()`.** Use `from utils.logger import get_logger`.
- **Never read env vars directly.** Use `from config.settings import settings`.
  Adding a key means updating `settings.py`, `.env.example`, and
  `docs/env_variables.md` in the same commit.
- **Routes return Pydantic schemas from `api/schemas.py`**, never raw dicts.
- **One router per domain**, in `api/routes/`, each with its own `prefix` and `tags`.

## Sessions

Routes take a session by dependency injection:

```python
@router.get("/leads", response_model=list[LeadResponse])
async def list_leads(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_leads(db)
```

Background code (agents, schedulers) that has no request uses the context
manager, which commits on success and rolls back on error:

```python
from db.database import session_scope

async with session_scope() as db:
    await crud.update_lead_stage(db, lead_id, "Qualified", "Score 87")
```

Synchronous code that genuinely cannot await — the APScheduler follow-up jobs —
imports `db.sync_crud` instead. It mirrors the same functions on a sync session
and returns plain dicts. It is a re-expression of `crud.py`, not a second source
of truth: business logic changes go in `crud.py` and get mirrored across.

## Error handling

Raise `HTTPException` with a message a person can act on:

```python
raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")
```

- 400 malformed input · 404 missing row · 409 conflicting state
- 422 valid shape, invalid value (unknown stage) · 503 a dependency is down

Never let an exception escape a background task — catch, log with
`log.exception(...)`, and record the failure in short-term memory.

## Cross-branch imports

`main.py` registers Ismail's and Sufiyan's routers with `importlib` inside a
try/except, and `api/orchestrator_bridge.py` wraps every call into
`agents/orchestrator.py` the same way. This is deliberate: a module that is
missing or mid-refactor on another branch must never stop the app from booting.

When you add a route that depends on another person's module, follow the same
pattern rather than importing it at module top level.

## Migrations

Models are the source of truth. After changing `db/models.py`:

```
cd backend
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

Then update `.claude/skills/database-schema.md`, `docs/database_schema.md`, and
`frontend/src/lib/types.ts` to match. `init_db()` on startup calls
`create_all()` so a fresh clone works without migrations, but it will not alter
an existing table — that is what Alembic is for.

## Layering

```
routes  →  crud / memory        (never call agents or comms directly)
agents  →  orchestrator → comms (agents never import comms themselves)
comms   →  sync_crud
```
