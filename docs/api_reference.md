# API Reference

Every endpoint: method, path, request body, response shape. This file is
**shared** (per `FOLDER_STRUCTURE.md`) — each teammate writes their own
section. This document currently contains only the **Emails**,
**Meetings**, and **Webhook** sections (Sufiyan's ownership, per
`sufiyan_work.md`). Ismail and Wajeeh: add your endpoint sections below
without editing these three — see `conflicts.md` for the general
low-conflict-merge approach this repo is using.

---

## Emails

Owner: `backend/api/routes/emails.py`. Registered at prefix `/emails`
(see `conflicts.md` for the exact `main.py` registration snippet — not
wired in yet).

### `GET /emails`

Returns every email the system has sent, across all leads.

**Response** — `200 OK`, array of:

```json
{
  "id": "email_a1b2c3d4",
  "lead_id": "lead_001",
  "contact_id": "contact_001",
  "subject": "Automate Your Customer Support — AlphaLogistics",
  "body": "...",
  "status": "sent",
  "sent_at": "2026-08-15T12:00:00+00:00"
}
```

`status` is one of `sent`, `failed`, `replied`. `sent_at` is `null` if the
email hasn't actually been dispatched (shouldn't normally happen — every
send attempt, success or failure, writes a record via `crud.create_email`).

### `POST /emails/send`

Sends an outreach email through Resend (or logs it in mock mode when
`RESEND_API_KEY` isn't configured — see `backend/comms/email_sender.py`)
and records it.

**Request body:**

```json
{
  "lead_id": "lead_001",
  "contact_id": "contact_001",
  "subject": "Automate Your Customer Support — AlphaLogistics",
  "body": "Hi Omar, ..."
}
```

Note: the body carries `contact_id`, not a raw email address — the route
resolves the send-to address via `crud.get_contact(contact_id)`.

**Response** — `200 OK`:

```json
{ "success": true, "message": "Email sent (email_id=re_abc123)" }
```

`success: false` cases: `contact_id` doesn't resolve to a known contact,
or the underlying Resend call failed — `message` carries the reason in
both cases.

---

## Meetings

Owner: `backend/api/routes/meetings.py`. Registered at prefix `/meetings`.

### `GET /meetings`

Returns every meeting on record — both live-created ones (via
`POST /meetings/create` or an inbound "Meeting Requested" classification)
and the one pre-loaded from `data/seeds/meetings_seed.json` at process
startup for demo purposes (see `backend/comms/_shim.py`).

**Response** — `200 OK`, array of:

```json
{
  "id": "meeting_e5f6a7b8",
  "lead_id": "lead_001",
  "contact_id": "contact_001",
  "meeting_link": "https://cal.com/admin/alphalogistics",
  "status": "link_sent",
  "scheduled_at": "2026-08-22T10:00:00+00:00",
  "briefing": {
    "customer_problem": "High volume of WhatsApp customer inquiries overwhelming 5-person support team",
    "recommended_service": "WhatsApp AI Chatbot with CRM Integration",
    "key_points": ["Ask about current response time SLA", "Mention 60% cost reduction case study"],
    "watch_out_for": ["Budget sign-off process", "IT approval for integrations"]
  },
  "admin_notified": false
}
```

`scheduled_at` and `briefing` are `null` until a real booking time and a
pre-meeting briefing exist — a meeting created via `POST /meetings/create`
starts with both unset; `briefing` is filled in later by
`MeetingManager.send_pre_meeting_reminder()`, which also flips
`admin_notified` to `true` once the admin's WhatsApp briefing goes out
(see `backend/comms/followup_scheduler.py`'s 5-minute reminder job).

### `POST /meetings/create`

Generates a booking link for a lead, records the meeting, emails the
prospect the link, and notifies the admin on WhatsApp — i.e. everything
`MeetingManager.handle_meeting_request()` does.

**Request body:**

```json
{ "lead_id": "lead_001" }
```

**Response** — `200 OK`:

```json
{
  "meeting_link": "https://cal.com/admin/alphalogistics",
  "email_sent": true,
  "whatsapp_sent": true
}
```

`meeting_link` is `null` (with both booleans `false`) if `lead_id` or its
primary contact can't be resolved. As of this writing, the booking link
generator (`tools/calendar_tool.py`, Ismail's) hasn't landed yet, so
`meeting_link` is a mock `https://cal.com/admin/<slug>` value rather than
a real Cal.com booking — see `conflicts.md` §4a.

---

## Webhook

Owner: `backend/api/routes/webhook.py`. Registered at prefix `/webhook`.

### `POST /webhook/email-reply`

Inbound endpoint that Resend (or a compatible inbound-email provider)
calls when a prospect replies to an outreach email. Delegates to
`EmailReader.process_inbound_reply()`, which matches the reply to its
original outbound email, records it, classifies it, and dispatches the
next pipeline action (see `backend/comms/email_reader.py`).

**Request body** — tolerant of a couple of common shapes; at minimum
needs a sender address, a subject, and a text body:

```json
{
  "data": {
    "from": "ceo@alphalogistics.ae",
    "subject": "Re: Automate Your Customer Support — AlphaLogistics",
    "text": "Sounds great, let's talk.",
    "created_at": "2026-08-15T12:34:00Z"
  }
}
```

`from` may also be an object (`{"email": "..."}`) or a
`"Name <email@x.com>"` formatted string — the handler extracts the bare
address either way. A flat (non-`"data"`-wrapped) body is also accepted.

**Response** — **always** `200 OK`, regardless of whether the payload was
recognized:

```json
{ "status": "ok" }
```

This is deliberate, not a bug: an inbound-email webhook provider will
retry a non-2xx response indefinitely, so a malformed or unexpected
payload is logged and swallowed rather than surfaced as an HTTP error.
Check application logs (`api.webhook` logger) for whether a given
delivery actually matched an outbound email — `matched: false` in the
log line means no action was taken.

---

*Sections above are Sufiyan's. Ismail (agent pipeline / RAG endpoints)
and Wajeeh (company/ICP/pipeline/leads endpoints, per
`FOLDER_STRUCTURE.md`'s `backend/api/routes/` list) — add your sections
below this line.*
