# Merge Notes — all three branches integrated

`wajeeh-branch` + `main` (Ismail's agents/RAG/tools) + `sufiyan-branch`
(comms/routes) are merged, and persistence moved from PostgreSQL to
**Cloud Firestore**. This supersedes the earlier `conflicts.md` checklist —
every item in it is now done.

---

## ⚠️ One thing is still required to run

**`FIREBASE_SERVICE_ACCOUNT_PATH` is not set,** and there is no service-account
JSON in the repo or the env file. Firestore is the datastore for everything,
so until that key exists:

- the backend starts and `/health` answers, but reports
  `"database": "unavailable: …"`
- every data route returns an error
- `python backend/load_seeds.py` exits with an actionable message

To fix: Firebase console → Project settings → Service accounts → *Generate new
private key*, save the JSON outside the repo, then set

```
FIREBASE_SERVICE_ACCOUNT_PATH=C:\path\to\your-service-account.json
```

Nothing else is missing. Everything else was verified live against the
supplied keys (see "Verified" below).

---

## What changed in the merge

### Imports normalised
Ismail's modules used `from backend.x import y`; mine and Sufiyan's used bare
`from x import y`. Left mixed, Python loads each module twice — two `settings`
singletons, two Firestore clients. All 23 files were rewritten to the bare
form, matching `CLAUDE.md`'s documented `cd backend && uvicorn main:app`.

### Postgres → Firestore
- **Deleted:** `db/database.py`, `db/sync_crud.py`, `db/migrations/`,
  `alembic.ini`, and the SQLAlchemy/Alembic/psycopg2 dependencies.
- **`db/firestore.py`** — client init (service account → ADC → emulator),
  collection names, and a `health()` probe.
- **`db/models.py`** — no longer an ORM. Document factories plus the shared
  stage/status constants everything imports.
- **`db/crud.py`** — rewritten on Firestore, **synchronous**, returns dicts.
  It implements Sufiyan's exact `_shim.py` contract (`get_meetings_needing_
  reminder`, `mark_meeting_admin_notified`, `get_contact`, …) *and* the richer
  functions my routes need, so **no file in `comms/` needed editing**.
- **`db/acrud.py`** — new. Async wrappers (`asyncio.to_thread`) so FastAPI
  handlers never block the event loop on the synchronous Firestore SDK.

Firestore has no joins and no cascades, so `delete_lead()` removes children
explicitly, and the inbox/lead-detail joins happen in Python. Compound
filtering is done in Python too, to avoid needing composite indexes.

### Anthropic → Gemini
`comms/_llm.py` was built on Claude; the key set is Gemini-only. It now
delegates to Ismail's `agents/llm_utils.py`, so there is one LLM client for
the whole project. `complete_json()` keeps its exact signature — the three
callers (classifier, follow-up scheduler, meeting manager) are untouched.

`gemini-2.0-flash` has been **retired** by Google and 404s. Default is now
`gemini-3.5-flash`, and `llm_utils` automatically retries on
`GEMINI_FALLBACK_MODEL` (`gemini-flash-latest`) if a named model disappears
again, rather than failing the run.

### Resend → SMTP
`EmailSender` now tries SMTP first, Resend second, mock third. The From
address is forced to `SMTP_USER` whenever SMTP is configured — the env file
had `SENDER_EMAIL=onboarding@resend.dev` left over from the Resend setup,
which Gmail would have rejected or spam-foldered.

### Config
Three `settings.py` files became one, covering Wajeeh's infra keys, Ismail's
RAG/pipeline tuning, and Sufiyan's comms keys. Two normalisers were needed for
the real env file:

- **`REDIS_URL`** was the entire `redis-cli --tls -u redis://…` command line.
  The validator extracts the URL, and upgrades `redis://` → `rediss://` when
  `--tls` is present (Upstash closes the connection without TLS).
- **`QDRANT_URL`** / blank values generally — an empty value in the env file
  no longer beats the code default.

`CAL_API_KEY` and `GEMINI_API_KEY` are the env-file names; `CALCOM_API_KEY`
and `GOOGLE_API_KEY` still work via the `cal_api_key` / `google_api_key`
properties.

### Dependency conflict worth knowing about
`qdrant-client` pulls the newest `grpcio-tools`, which drags in protobuf 7 and
**silently breaks the Gemini SDK** (it needs <6). `google-cloud-firestore`
≥2.20 also demands protobuf ≥6. The working triple is pinned in
`requirements.txt`: `google-cloud-firestore==2.19.0`, `grpcio-tools==1.68.1`,
`protobuf>=5.26.1,<6`. `pip check` is clean. Don't bump one without the others.

`fastembed` was dropped — Gemini embeddings are used when a key is set, and it
pulls a very large onnxruntime download.

### Routers
`main.py` registers all eight routers. Sufiyan's define their paths without a
prefix, so they are mounted at `/emails`, `/meetings`, `/webhook`, giving
exactly the URLs the frontend already calls. My `dashboard.py` now serves only
`GET /inbox` — its `/emails` and `/meetings` stand-ins were deleted now that
the real ones exist.

---

## Verified live against the supplied keys

| Integration | Result |
|---|---|
| Gemini (agents) | ✅ real call returned valid JSON |
| Gemini (comms classifier + follow-up) | ✅ classified a reply as "Meeting Requested" |
| Qdrant Cloud | ✅ reachable, 0 collections |
| Tavily | ✅ search returned results |
| Gmail SMTP | ✅ STARTTLS login succeeded (no mail sent) |
| Redis (Upstash) | ✅ PING + set/get round-trip over TLS |
| **Firestore** | ❌ **no credentials — see the top of this file** |

Backend logic (CRUD, follow-up rules, reply flow, stage transitions, dedupe,
timeline, cascading delete) and all HTTP routes pass an end-to-end suite run
against an injected in-memory Firestore stand-in. That exercises our query and
business logic; it does not exercise the Google SDK's own behaviour, which
needs the service-account key.

Frontend `npm run build` passes (tsc + vite, 140 modules).

---

## Cleanup pass (done after the merge commit)

- Deleted `comms/_shim.py`, `comms/_firestore_crud.py`, and
  `comms/requirements-comms.txt`. `_deps.py` is now three plain imports.
  **Salvaged first:** the shim's `get_logger()` carried a UTF-8 console fix
  that stops the emoji in the WhatsApp templates raising
  `UnicodeEncodeError` on a Windows console. It now lives in
  `utils/logger.py::_make_console_utf8_safe()`.
- `backend/Dockerfile` no longer installs `build-essential`/`libpq-dev` —
  those were only ever for psycopg2.
- Docs brought in line with reality: root `CLAUDE.md`, `FOLDER_STRUCTURE.md`
  (stack table + `db/` tree), `.claude/settings.json` (dropped the alembic
  permission, added deny rules for the env file and service-account JSON).
- Added `docs/architecture.md` and `docs/database_schema.md`, both listed in
  `FOLDER_STRUCTURE.md` but never written.
- `conflicts.md` now opens with a SUPERSEDED banner — it still described
  Postgres as the team database.
- `test_comms.py` labels fixed (it announced "Claude (anthropic)" and a shim
  that no longer exists).

## Still outstanding

- **Firebase service-account key** (see the top of this file) — the only
  thing standing between this repo and a working demo.
- **WhatsApp** is off by request. `whatsapp_notifier.py` logs instead of
  sending while the Twilio keys are blank.
- **Playwright browsers** are not downloaded locally — run
  `playwright install chromium` before a live pipeline run. The Docker image
  already does this.
- `backend/test_comms.py` needs Firestore plus seeded data to run:
  `python backend/load_seeds.py && cd backend && python test_comms.py`.
