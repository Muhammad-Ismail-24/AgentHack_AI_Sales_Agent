# Database Schema — Firestore

Source of truth: `backend/db/models.py` (document factories) and
`backend/db/firestore.py` (collection names). Persistence is Cloud Firestore;
there is no ORM and no migrations.

Document IDs are UUID4 strings, except seeded demo data which uses readable
ids (`lead_001`, `lead_001_contact_1`, `email_001`). All timestamps are
timezone-aware UTC.

Collections are flat and related by id fields — **Firestore has no joins**, so
anything that looks like one is done in Python in `db/crud.py`.

## leads

| Field | Type | Notes |
|---|---|---|
| id | string | document id |
| company_name | string | required |
| website / industry / location | string \| null | |
| employee_count | int \| null | |
| pipeline_stage | string | default `Discovered` |
| lead_score | int \| null | 0–100, clamped on write |
| score_explanation | string \| null | why the score is what it is |
| recommended_service | string \| null | from the service-matching agent |
| pitch_angle | string \| null | |
| icp_fit | bool \| null | |
| research_summary | string \| null | |
| apollo_data | map \| null | raw enrichment payload |
| session_id | string \| null | scopes a pipeline run |
| created_at / updated_at | timestamp | |

## contacts

id · lead_id · name · role · email · phone · linkedin_url · is_primary (bool) ·
created_at

`phone` (added for the WhatsApp extra-credit feature): when set,
`comms/meeting_manager.py` also messages the contact directly via Green API
on meeting confirmation. `None` unless explicitly set — no enrichment agent
populates it yet.

## emails

id · lead_id · contact_id · subject · body · status (default `draft`) ·
sent_at · created_at

## replies

id · email_id · raw_body · classification · summary · next_action · received_at

## meetings

id · lead_id · contact_id · meeting_link · scheduled_at · briefing (map) ·
admin_notified (bool) · status (default `link_sent`) · created_at

## followups

id · lead_id · original_email_id · followup_email_id · scheduled_for ·
status (default `pending`) · created_at

## pipeline_events

id · lead_id · from_stage · to_stage · reason · created_at

One document per stage transition — this is what the lead-detail timeline renders.

## Enum values (plain strings)

**pipeline_stage** — active: `Discovered`, `Potential`, `Researching`,
`Qualified`, `Contacted`, `Interested`, `Meeting Scheduled`, `Converted`;
rejected: `Not Qualified`, `Not Interested`, `Do Not Contact`

**emails.status** — `draft`, `sent`, `failed`, `replied`

**meetings.status** — `link_sent`, `confirmed`, `completed`, `cancelled`

**followups.status** — `pending`, `sent`, `cancelled`

**replies.classification** — `Interested`, `Pricing Objection`,
`Not Interested`, `Meeting Requested`, `Out of Office`, `Unclear`

Import these from `db/models.py` (`PIPELINE_STAGES`, `ACTIVE_STAGES`,
`REJECTED_STAGES`, `EMAIL_STATUSES`, `MEETING_STATUSES`, `FOLLOWUP_STATUSES`,
`CLASSIFICATIONS`) rather than retyping the strings.

## Behaviour worth knowing

- `crud.update_lead_stage()` writes a `pipeline_events` document automatically.
  Never set `pipeline_stage` by hand or the timeline loses the transition.
- `crud.create_reply()` flips the parent email's status to `replied`.
- `crud.upsert_leads_from_pipeline()` dedupes on `company_name` within a
  `session_id` and returns each lead once even if the batch repeats it.
- `crud.get_emails_needing_followup(days=3)` = status `sent`, `sent_at` older
  than the cutoff, no reply document, and no `pending`/`sent` follow-up. The
  cross-collection parts are evaluated in Python — Firestore has no NOT-IN
  across collections.
- **Deletes do not cascade.** `crud.delete_lead()` removes contacts, emails,
  replies, meetings, follow-ups, and events explicitly. Anything that deletes
  a parent must do the same.
- `crud._where()` supports single-field equality only. Compound filtering is
  done in Python to avoid needing composite indexes.

## Credentials

`FIREBASE_SERVICE_ACCOUNT_PATH`, then Application Default Credentials, or
`FIRESTORE_EMULATOR_HOST` for local work. `db/firestore.py` raises
`FirestoreUnavailable` with an actionable message rather than an SDK
stack trace; `fs.is_available()` checks without raising.
