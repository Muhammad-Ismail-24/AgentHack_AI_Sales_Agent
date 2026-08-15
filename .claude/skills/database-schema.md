# Database Schema

Source of truth: `backend/db/models.py`. IDs are UUID4 strings in `String(36)`
columns. All timestamps are timezone-aware UTC.

## leads

| Column | Type | Notes |
|---|---|---|
| id | String(36) | PK |
| company_name | String(255) | not null, indexed |
| website | String(512) | |
| industry | String(255) | |
| location | String(255) | |
| employee_count | Integer | |
| pipeline_stage | String(64) | not null, default `Discovered`, indexed |
| lead_score | Integer | 0–100, clamped on write |
| score_explanation | Text | why the score is what it is |
| recommended_service | String(255) | from the service-matching agent |
| pitch_angle | Text | |
| icp_fit | Boolean | |
| research_summary | Text | |
| apollo_data | JSON | raw enrichment payload |
| session_id | String(64) | indexed — scopes a pipeline run |
| created_at / updated_at | DateTime(tz) | |

## contacts

id · lead_id (FK leads.id, CASCADE) · name · role · email(320) ·
linkedin_url · is_primary (Boolean, default false) · created_at

## emails

id · lead_id (FK leads.id, CASCADE) · contact_id (FK contacts.id, SET NULL) ·
subject(512) · body (Text) · status (default `draft`) · sent_at · created_at

## replies

id · email_id (FK emails.id, CASCADE) · raw_body · classification(64) ·
summary · next_action(512) · received_at

## meetings

id · lead_id (FK leads.id, CASCADE) · contact_id (FK contacts.id, SET NULL) ·
meeting_link(512) · scheduled_at · briefing (JSON) ·
admin_notified (Boolean, default false) · status (default `link_sent`) · created_at

## followups

id · lead_id (FK leads.id, CASCADE) · original_email_id (FK emails.id, CASCADE) ·
followup_email_id (FK emails.id, SET NULL, nullable) · scheduled_for ·
status (default `pending`) · created_at

## pipeline_events

id · lead_id (FK leads.id, CASCADE) · from_stage · to_stage · reason(512) · created_at

One row per stage transition. This is what the lead-detail timeline renders.

## Enum values (plain strings, not DB enums)

**pipeline_stage** — active: `Discovered`, `Potential`, `Researching`,
`Qualified`, `Contacted`, `Interested`, `Meeting Scheduled`, `Converted`;
rejected: `Not Qualified`, `Not Interested`, `Do Not Contact`

**emails.status** — `draft`, `sent`, `failed`, `replied`

**meetings.status** — `link_sent`, `confirmed`, `completed`, `cancelled`

**followups.status** — `pending`, `sent`, `cancelled`

**replies.classification** — `Interested`, `Pricing Objection`, `Not Interested`,
`Meeting Requested`, `Out of Office`, `Unclear`

The lists live in `backend/db/models.py` as `PIPELINE_STAGES`, `ACTIVE_STAGES`,
`REJECTED_STAGES`, `EMAIL_STATUSES`, `MEETING_STATUSES`, `FOLLOWUP_STATUSES`,
and `CLASSIFICATIONS` — import them rather than retyping the strings.

## Behaviour worth knowing

- `crud.update_lead_stage()` writes a `pipeline_events` row automatically.
  Never set `pipeline_stage` by hand or the timeline loses the transition.
- `crud.create_reply()` flips the parent email's status to `replied`.
- `crud.upsert_leads_from_pipeline()` dedupes on `company_name` within a
  `session_id`, and returns each lead once even if the batch repeats it.
- `crud.get_emails_needing_followup(days=3)` = status `sent`, `sent_at` older
  than the cutoff, no reply row, and no follow-up already `pending`/`sent`.
- Deleting a lead cascades to its contacts, emails, replies, meetings,
  follow-ups, and events.
