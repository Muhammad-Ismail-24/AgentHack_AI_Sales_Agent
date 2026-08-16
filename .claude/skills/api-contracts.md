# API Contracts

Base URL `http://localhost:8000`. Interactive docs at `/docs`.
Wajeeh's schemas live in `backend/api/schemas.py`; Sufiyan's routers define
their own locally. The frontend mirrors both in `frontend/src/lib/types.ts`
and calls everything through `frontend/src/lib/api.ts`.

All three branches are merged — every endpoint below is live.

---

## Meta — Wajeeh

| Method | Path | Response | File |
|---|---|---|---|
| GET | `/` | `{name, docs, health}` | `main.py` |
| GET | `/health` | `{status, database, version}` | `main.py` |

`/health` returns 200 even when Firestore is unreachable — the `database`
field carries the detail (`ok`, `unavailable: …`, `unreachable: …`). It is a
liveness check, not a readiness gate.

---

## Company — Wajeeh · `api/routes/company.py`

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/company/upload` | multipart `file` (.pdf/.txt/.md, ≤20 MB) | `CompanyUploadResponse` |
| POST | `/company/text` | `{text, company_name?}` | `CompanyUploadResponse` |

`CompanyUploadResponse` = `{session_id, company_name, status, chars_ingested, message?}`

`session_id` is minted here and threads through every later call.
Errors: 400 empty/unsupported · 413 too large · 422 no extractable text.

---

## ICP — Wajeeh · `api/routes/icp.py`

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/icp/define` | `{session_id, location, industry, company_size, special_focus?}` | `{session_id, icp}` |
| GET | `/icp/{session_id}` | — | `{session_id, icp}` |

404 if the session has no company info yet. The ICP lives in Redis on the
session, not in Firestore.

---

## Pipeline — Wajeeh · `api/routes/pipeline.py`

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/pipeline/start` | `{session_id}` | `{session_id, status}` |
| GET | `/pipeline/status/{session_id}` | — | `PipelineStatusResponse` |
| POST | `/pipeline/stop/{session_id}` | — | `{session_id, status}` |

`PipelineStatusResponse` = `{session_id, stage, is_running, raw_leads_count,
filtered_count, qualified_count, outreach_count, total_leads, stage_counts, error}`

Poll status every 3s while `is_running`. Errors on start: 404 missing
company/ICP · 409 already running · 503 orchestrator unavailable.

Stage names the frontend progress bar recognises: `Ingesting company`,
`Defining ICP`, `Discovering leads`, `Filtering leads`, `Researching leads`,
`Qualifying leads`, `Matching services`, `Finding decision makers`,
`Writing emails`, then `complete` / `failed` / `idle`.

---

## Leads — Wajeeh · `api/routes/leads.py`

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/leads?session_id=&stage=` | — | `LeadResponse[]` (contacts nested) |
| GET | `/leads/{lead_id}` | — | `LeadDetailResponse` |
| PATCH | `/leads/{lead_id}` | `LeadUpdateRequest` | `LeadResponse` |
| DELETE | `/leads/{lead_id}` | — | `{success, message}` |

`LeadDetailResponse` = `{lead, contacts[], emails[], replies[], meetings[], events[]}`

`LeadUpdateRequest` — all optional: `pipeline_stage`, `lead_score` (0–100),
`recommended_service`, `pitch_angle`, `research_summary`, `icp_fit`.
A stage change records a `pipeline_events` document with reason
"Moved manually". 422 if `pipeline_stage` is not in `PIPELINE_STAGES`.

DELETE removes the lead's contacts, emails, replies, meetings, follow-ups, and
events explicitly — Firestore has no cascades.

---

## Inbox — Wajeeh · `api/routes/dashboard.py`

| Method | Path | Response |
|---|---|---|
| GET | `/inbox` | `InboxItem[]` |

`InboxItem` = `{reply, email, lead_id, company_name, contact_name}` — the join
is done server-side because Firestore cannot do it in a query, so the Inbox
page renders straight off this.

---

## Emails — Sufiyan · `api/routes/emails.py` (mounted at `/emails`)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/emails` | — | `EmailSchema[]` |
| POST | `/emails/send` | `{lead_id, contact_id, subject, body}` | `{success, message}` |

Sending goes through `EmailSender`, which prefers SMTP, falls back to Resend,
and drops to mock mode when neither is configured. Every attempt is recorded
in Firestore with status `sent` or `failed`.

---

## Meetings — Sufiyan · `api/routes/meetings.py` (mounted at `/meetings`)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/meetings` | — | `MeetingSchema[]` |
| POST | `/meetings/create` | `{lead_id, contact_id?}` | `{meeting_link, meeting_id}` |

---

## Webhook — Sufiyan · `api/routes/webhook.py` (mounted at `/webhook`)

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/webhook/email-reply` | provider payload | `{success}` |

Flow: match the sender via `crud.get_contact_by_email()` → match the thread via
`crud.find_email_by_subject()` (the `Re:` prefix is stripped first) → classify
with Gemini → `crud.create_reply()` (which flips the email to `replied`) →
advance the lead's stage.

---

## Intelligence layer · `api/routes/intelligence.py`

Extras that sit beside the pipeline, not inside it. Every POST is triggered by
a human click — the debate and the autopsy each spend LLM calls, and the audio
one spends TTS credit, so none of them runs automatically.

**These run on Groq** (`agents/groq_utils.py`, `GROQ_API_KEY`), not Gemini.
The pipeline and the original comms features keep `agents/llm_utils.py` and
`GEMINI_API_KEY` to themselves — two providers, two quotas, two rate limiters.
The one exception is the RAG lookup inside the debate, which must stay on
Gemini embeddings because that is what vectorised the Qdrant collections.

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/intelligence/leads/{id}/devils-advocate` | — | `VerdictResponse` |
| GET | `/intelligence/leads/{id}/devils-advocate` | — | `VerdictResponse` |
| POST | `/intelligence/leads/{id}/autopsy` | — | `AutopsyResponse` |
| GET | `/intelligence/leads/{id}/autopsy` | — | `AutopsyResponse` |
| GET | `/intelligence/autopsies/insights` | — | `AutopsyInsightsResponse` |
| POST | `/intelligence/meetings/{id}/whisper` | — | `WhisperResponse` |
| GET | `/intelligence/meetings/{id}/whisper` | — | `WhisperResponse` |
| POST | `/intelligence/meetings/{id}/whisper/audio` | — | `WhisperAudioResponse` |

Status codes worth knowing:

- **404 on a GET** means the debate/autopsy/script has never been generated —
  a normal empty state, which `api.ts` turns into `null` rather than a throw.
- **409 on `POST .../autopsy`** means the lead is still active. An autopsy only
  runs on a lead in a rejected stage.
- **503 on any POST** means `agents/orchestrator.py` could not be imported.
  These endpoints have no useful fallback, so they say so rather than
  fabricating a verdict.
- **200 with `audio_url: null`** from the audio endpoint is the no-TTS-key
  outcome, not a failure — `message` explains it, and the text script is
  unaffected.

Generated audio is served read-only from `/audio` (mounted in `main.py` from
`settings.AUDIO_DIR`). The frontend resolves those paths through
`resolveMediaUrl()` so they go back through the dev proxy.

---

## Conventions

- All bodies are JSON except `/company/upload`, which is multipart.
- Timestamps are ISO 8601 UTC.
- Errors are FastAPI's `{"detail": "..."}` — `detail` is written for a human
  and is safe to surface in a toast.
- CORS is open to all origins (hackathon build).
