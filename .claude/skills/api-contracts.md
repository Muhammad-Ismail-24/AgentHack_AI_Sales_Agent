# API Contracts

Base URL `http://localhost:8000`. Interactive docs at `/docs`.
Schemas live in `backend/api/schemas.py`; the frontend mirrors them in
`frontend/src/lib/types.ts`. Every frontend call goes through
`frontend/src/lib/api.ts`.

Status: ✅ built · ⏳ not built yet on this branch

---

## Meta — Wajeeh

| Method | Path | Response | File | |
|---|---|---|---|---|
| GET | `/` | `{name, docs, health}` | `main.py` | ✅ |
| GET | `/health` | `{status, database, version}` | `main.py` | ✅ |

`/health` returns 200 even when the database is unreachable — the `database`
field carries the detail. It is a liveness check, not a readiness gate.

---

## Company — Wajeeh · `api/routes/company.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| POST | `/company/upload` | multipart `file` (.pdf/.txt/.md, ≤20 MB) | `CompanyUploadResponse` | ✅ |
| POST | `/company/text` | `{text, company_name?}` | `CompanyUploadResponse` | ✅ |

`CompanyUploadResponse` = `{session_id, company_name, status, chars_ingested, message?}`

`session_id` is minted here and threads through every later call.
Errors: 400 empty/unsupported · 413 too large · 422 no extractable text.

---

## ICP — Wajeeh · `api/routes/icp.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| POST | `/icp/define` | `{session_id, location, industry, company_size, special_focus?}` | `{session_id, icp}` | ✅ |
| GET | `/icp/{session_id}` | — | `{session_id, icp}` | ✅ |

404 if the session has no company info yet. The ICP is stored in Redis on the
session, not in the database.

---

## Pipeline — Wajeeh · `api/routes/pipeline.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| POST | `/pipeline/start` | `{session_id}` | `{session_id, status}` | ✅ |
| GET | `/pipeline/status/{session_id}` | — | `PipelineStatusResponse` | ✅ |
| POST | `/pipeline/stop/{session_id}` | — | `{session_id, status}` | ✅ |

`PipelineStatusResponse` = `{session_id, stage, is_running, raw_leads_count,
filtered_count, qualified_count, outreach_count, total_leads, stage_counts, error}`

Poll status every 3s while `is_running`. Errors on start: 404 missing
company/ICP · 409 already running · 503 agent pipeline unavailable.

---

## Leads — Wajeeh · `api/routes/leads.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| GET | `/leads?session_id=&stage=` | — | `LeadResponse[]` (contacts nested) | ✅ |
| GET | `/leads/{lead_id}` | — | `LeadDetailResponse` | ✅ |
| PATCH | `/leads/{lead_id}` | `LeadUpdateRequest` | `LeadResponse` | ✅ |
| DELETE | `/leads/{lead_id}` | — | `{success, message}` | ✅ |

`LeadDetailResponse` = `{lead, contacts[], emails[], replies[], meetings[], events[]}`

`LeadUpdateRequest` — all optional: `pipeline_stage`, `lead_score` (0–100),
`recommended_service`, `pitch_angle`, `research_summary`, `icp_fit`.
A stage change here records a `pipeline_events` row with reason "Moved manually".
422 if `pipeline_stage` is not in `PIPELINE_STAGES`.

---

## Dashboard reads — Wajeeh · `api/routes/dashboard.py`

| Method | Path | Response | |
|---|---|---|---|
| GET | `/inbox` | `InboxItem[]` | ✅ |
| GET | `/emails` | `EmailResponse[]` | ✅ fallback |
| GET | `/meetings` | `MeetingResponse[]` | ✅ fallback |

`InboxItem` = `{reply, email, lead_id, company_name, contact_name}` — the Inbox
page renders straight off this, no client-side joining.

`/emails` and `/meetings` here are read-only stand-ins. This router is
registered **after** Sufiyan's in `main.py`, so once his land, his handlers
match first and these can be deleted.

---

## Emails — Sufiyan · `api/routes/emails.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| GET | `/emails` | — | `EmailResponse[]` | ⏳ |
| POST | `/emails/send` | `{lead_id, contact_id, subject, body}` | `{success, message}` | ⏳ |

`POST /emails/send` should call `EmailSender.send()` then
`crud.update_email_status(email_id, "sent")`.

---

## Meetings — Sufiyan · `api/routes/meetings.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| GET | `/meetings` | — | `MeetingResponse[]` | ⏳ |
| POST | `/meetings/create` | `{lead_id, contact_id?}` | `{meeting_link, meeting_id}` | ⏳ |

---

## Webhook — Sufiyan · `api/routes/webhook.py`

| Method | Path | Request | Response | |
|---|---|---|---|---|
| POST | `/webhook/email-reply` | provider payload | `{success}` | ⏳ |

Flow: match sender via `crud.get_contact_by_email()` → match the thread via
`crud.find_email_by_subject()` (strip the `Re:` prefix first) → classify →
`crud.create_reply()` (which flips the email to `replied`) → advance the lead's
stage.

---

## Conventions

- All bodies are JSON except `/company/upload`, which is multipart.
- Timestamps are ISO 8601 UTC.
- Errors are FastAPI's `{"detail": "..."}` — `detail` is written for a human
  and is safe to surface in a toast.
- CORS is open to all origins (hackathon build).
