# Sufiyan — Work Breakdown (30%)
## Role: Communications, Outreach & Meeting Automation

You own everything that happens *after* the AI decides to contact a lead — sending the
email, reading the reply, classifying it, scheduling follow-ups, booking meetings, and
notifying the admin on WhatsApp. This is the automation layer that makes the system feel
like a real sales team running 24/7 without anyone touching it.

**Your folders:**
- `backend/comms/` — full ownership
- `backend/api/routes/emails.py` — full ownership
- `backend/api/routes/meetings.py` — full ownership
- `backend/api/routes/webhook.py` — full ownership
- `data/seeds/replies_seed.json` — you create this for the demo
- `data/seeds/meetings_seed.json` — you create this for the demo

---

## What You Are Building — Full Description

### 1. Email Sender
The system must send personalised outreach emails through Resend (the email API).
You build a clean sender that takes a contact email, subject, and body and fires the email.
It must also store every sent email in the database so the pipeline knows what was sent,
when, and to whom.

### 2. Email Reader (Inbox Polling)
The system polls the inbox every N minutes looking for replies. When a reply arrives
it is matched to the original outbound email and lead. The raw reply body is stored
and passed to the response classifier.

### 3. Response Classifier
When a prospect replies, Claude reads the email and classifies it into one of these
categories: Interested, Meeting Requested, Question, Pricing Objection, Technical Objection,
Not Interested, Not Now, Wrong Person / Referral, Other.

Based on the classification, the system decides the next action automatically:
- Interested → move lead to "Interested" stage, queue a meeting link reply
- Meeting Requested → generate a Cal.com link, send it immediately
- Question → draft a reply using company RAG knowledge, queue for review
- Not Interested → mark lead as "Not Interested", stop follow-up
- Not Now → schedule a follow-up in 14 days
- Wrong Person → ask Claude to identify who the right person is and reach out to them

### 4. Follow-Up Scheduler
If a lead receives an outreach email but does not reply after 3 days, the system
automatically sends a follow-up email. You build this using APScheduler — a background
job that wakes up, checks which leads need a follow-up, and fires email #2.

The follow-up email is shorter and different from the first. It references the previous
email and asks if the timing was wrong. Claude writes it using a dedicated prompt
(you add this prompt to `backend/config/prompts.py`).

### 5. Meeting Manager
When a meeting is confirmed (either because the prospect said yes or the classifier
detected a meeting request), you:
- Call the Cal.com API to generate a real booking link
- Store the meeting details in the database (lead_id, contact, link, scheduled time)
- Send a confirmation email to the prospect with the link
- Trigger the admin WhatsApp notification

### 6. WhatsApp Notifier (Extra Feature — Bonus Points)
When a meeting is confirmed, you send the admin a WhatsApp message via Twilio with:
- Company name
- Contact name and role
- Meeting time
- The meeting link

You also build a 30-minute pre-meeting reminder that fires via APScheduler and sends
the admin another WhatsApp message with a short briefing: customer problem, recommended
service, key questions to ask, and any objections raised during the email thread.

### 7. API Routes for Comms
You own the three API routes that connect your comms layer to the frontend:
- `POST /emails/send` — Wajeeh's frontend calls this to trigger sending an email
- `GET /emails` — returns all sent emails and their status
- `POST /webhook/email-reply` — the inbound webhook that Resend or Gmail calls when a reply arrives
- `GET /meetings` — returns all meetings
- `POST /meetings/create` — manually create a meeting from the frontend

---

## Steps for Claude Code to Follow

Work inside `backend/` throughout. You need Ismail's `backend/db/` and `backend/utils/`
to be set up first before Step 4 onwards — coordinate with Wajeeh (he sets up the DB layer).
For Steps 1–3 you can work independently.

---

### STEP 1 — Email Sender
**Prompt to give Claude Code:**
```
Build backend/comms/email_sender.py

Install: pip install resend

Create an EmailSender class:

__init__(self):
  - Load RESEND_API_KEY from settings
  - Set the from address from settings (SENDER_EMAIL)
  - Initialise resend client

async send(self, to_email: str, subject: str, body: str,
           lead_id: str, contact_id: str) -> dict:
  - Send the email via resend.Emails.send()
  - On success: log "Email sent to {to_email}" and return {success: True, email_id: resend_id}
  - On failure: log the error and return {success: False, error: str}
  - After sending (success or fail): call crud.create_email() to store in DB
    with fields: lead_id, contact_id, subject, body, status ("sent" or "failed"), sent_at

Also add to .env.example: RESEND_API_KEY, SENDER_EMAIL
```

---

### STEP 2 — Response Classifier
**Prompt to give Claude Code:**
```
Build backend/comms/response_classifier.py

Add FOLLOWUP_EMAIL_PROMPT and RESPONSE_CLASSIFIER_PROMPT to backend/config/prompts.py first:

RESPONSE_CLASSIFIER_PROMPT:
  System: You are a B2B sales assistant. Classify this email reply into exactly one category.
  Categories: Interested | Meeting Requested | Question | Pricing Objection |
  Technical Objection | Not Interested | Not Now | Wrong Person | Other
  User template: receives reply_body, original_email_subject, company_name
  Output: JSON {classification: str, summary: str, suggested_next_action: str}

Then build ResponseClassifier class in response_classifier.py:

async classify(self, reply_body: str, original_subject: str,
               company_name: str) -> dict:
  - Calls Claude (claude-sonnet-4-6) with RESPONSE_CLASSIFIER_PROMPT
  - Parses JSON response
  - Returns {classification, summary, suggested_next_action}

async decide_next_action(self, classification: str, lead_id: str) -> str:
  - "Interested" → update lead pipeline_stage to "Interested" in DB, return "stage_updated"
  - "Meeting Requested" → return "send_meeting_link"
  - "Not Interested" → update stage to "Not Interested", return "stop"
  - "Not Now" → schedule a 14-day follow-up, return "followup_scheduled"
  - "Wrong Person" → return "find_new_contact"
  - Everything else → return "queue_for_review"
```

---

### STEP 3 — Follow-Up Scheduler
**Prompt to give Claude Code:**
```
Build backend/comms/followup_scheduler.py

Add FOLLOWUP_EMAIL_PROMPT to backend/config/prompts.py:
  System: You are a B2B sales assistant writing a short follow-up email.
  The prospect did not reply to the first email. Be brief, low-pressure, warm.
  Max 80 words. Reference the previous email topic.
  User template: receives original_subject, original_body_summary, contact_name,
  company_name, recommended_service
  Output: JSON {subject: str, body: str}

Build the scheduler:

from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()

def start_scheduler():
  - Add job: check_and_send_followups() runs every 6 hours
  - scheduler.start()

async check_and_send_followups():
  - Query DB for emails where:
    * status == "sent"
    * sent_at < (now - 3 days)
    * no reply received (no entry in replies table for this email_id)
    * followup not already sent (check followups table)
  - For each qualifying email:
    * Call Claude with FOLLOWUP_EMAIL_PROMPT
    * Send follow-up email via EmailSender
    * Create entry in followups table in DB
    * Log: "Follow-up sent to {company_name}"

Call start_scheduler() from backend/main.py on app startup using @app.on_event("startup")
```

---

### STEP 4 — Email Reader / Inbound Webhook
**Prompt to give Claude Code:**
```
Build backend/comms/email_reader.py and the webhook route.

backend/comms/email_reader.py:
  class EmailReader:
    async process_inbound_reply(self, from_email: str, subject: str,
                                body: str, timestamp: str) -> dict:
      - Find the original email in DB by matching subject line (look for "Re: {original_subject}")
        or from_email matching a known contact
      - If found: store reply in replies table with {email_id, raw_body, received_at}
        and update original email status to "replied"
      - Classify the reply via ResponseClassifier.classify()
      - Call ResponseClassifier.decide_next_action()
      - If next_action == "send_meeting_link": call MeetingManager.handle_meeting_request()
      - Return {matched: bool, classification: str, next_action: str}

backend/api/routes/webhook.py:
  POST /webhook/email-reply
  - Accepts Resend inbound webhook payload (JSON)
  - Extracts from_email, subject, text body
  - Calls EmailReader.process_inbound_reply()
  - Returns 200 OK (always — webhook must not fail)

Note: Register this route in backend/main.py
```

---

### STEP 5 — Meeting Manager
**Prompt to give Claude Code:**
```
Build backend/comms/meeting_manager.py

Add MEETING_BRIEFING_PROMPT to backend/config/prompts.py:
  System: You are a sales coach preparing an admin for a meeting.
  Write a short briefing: customer problem, recommended service, key points to raise,
  any objections from the email thread.
  User template: receives company_name, research_summary, recommended_service,
  email_thread_summary (list of email + reply texts)
  Output: JSON {customer_problem: str, recommended_service: str,
  key_points: list[str], watch_out_for: list[str]}

class MeetingManager:

  async handle_meeting_request(self, lead_id: str) -> dict:
    - Fetch lead + contact from DB
    - Generate booking link via calendar_tool.generate_booking_link()
    - Store meeting in DB: {lead_id, contact_id, meeting_link, status: "link_sent"}
    - Send confirmation email via EmailSender with the booking link
    - Send WhatsApp notification via WhatsAppNotifier
    - Update lead pipeline_stage to "Meeting Scheduled"
    - Return {meeting_link, email_sent: bool, whatsapp_sent: bool}

  async send_pre_meeting_reminder(self, meeting_id: str) -> None:
    - Fetch meeting + lead + all emails/replies from DB
    - Build email_thread_summary from stored email bodies
    - Call Claude with MEETING_BRIEFING_PROMPT to generate briefing
    - Send WhatsApp message via WhatsAppNotifier with the full briefing
    - Log "Pre-meeting reminder sent for {company_name}"

  Schedule the pre_meeting_reminder job in followup_scheduler.py:
    - Every 5 minutes check for meetings where scheduled_at is within 35 minutes
      and admin_notified == False
    - Call send_pre_meeting_reminder() and set admin_notified = True
```

---

### STEP 6 — WhatsApp Notifier
**Prompt to give Claude Code:**
```
Build backend/comms/whatsapp_notifier.py

Install: pip install twilio

class WhatsAppNotifier:

  __init__(self):
    - Load TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM,
      ADMIN_WHATSAPP_NUMBER from settings
    - Init Twilio client

  async send_meeting_confirmed(self, company_name: str, contact_name: str,
                               contact_role: str, meeting_link: str,
                               scheduled_time: str) -> bool:
    - Build message:
      "✅ Meeting Confirmed!
       Company: {company_name}
       Contact: {contact_name} ({contact_role})
       Time: {scheduled_time}
       Link: {meeting_link}"
    - Send to ADMIN_WHATSAPP_NUMBER via Twilio WhatsApp sandbox
    - Return True on success, False on failure, log both

  async send_pre_meeting_briefing(self, company_name: str,
                                  briefing: dict) -> bool:
    - Build message:
      "⏰ Meeting in 30 minutes — {company_name}
       Problem: {briefing.customer_problem}
       Pitch: {briefing.recommended_service}
       Key points: {briefing.key_points joined with bullet}
       Watch out: {briefing.watch_out_for joined with bullet}"
    - Send to ADMIN_WHATSAPP_NUMBER
    - Return True/False

Add to .env.example:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
  TWILIO_WHATSAPP_FROM, ADMIN_WHATSAPP_NUMBER
```

---

### STEP 7 — API Routes
**Prompt to give Claude Code:**
```
Build the three API route files you own.

backend/api/routes/emails.py:
  GET /emails
    - Query all emails from DB (use crud.get_all_emails())
    - Return list of EmailSchema
  POST /emails/send
    - Body: {lead_id, contact_id, subject, body}
    - Call EmailSender.send()
    - Return {success, message}

backend/api/routes/meetings.py:
  GET /meetings
    - Query all meetings from DB (use crud.get_all_meetings())
    - Return list of MeetingSchema
  POST /meetings/create
    - Body: {lead_id}
    - Call MeetingManager.handle_meeting_request(lead_id)
    - Return {meeting_link, email_sent, whatsapp_sent}

backend/api/routes/webhook.py:
  POST /webhook/email-reply
    - Already built in Step 4, just make sure it's registered in main.py

Make sure all three route files are imported and included in backend/main.py with
their respective prefixes:
  app.include_router(emails_router, prefix="/emails")
  app.include_router(meetings_router, prefix="/meetings")
  app.include_router(webhook_router, prefix="/webhook")
```

---

### STEP 8 — Demo Seed Data
**Prompt to give Claude Code:**
```
Create the demo seed files for the comms layer.

data/seeds/replies_seed.json:
  Create 3 sample replies for 3 different leads:
  [
    {
      "lead_id": "lead_001",
      "from_email": "ceo@alphalogistics.ae",
      "subject": "Re: Automate Your Customer Support — AlphaLogistics",
      "body": "Hi, this looks interesting. We've been struggling with WhatsApp volume. Can we schedule a call this week?",
      "expected_classification": "Meeting Requested"
    },
    {
      "lead_id": "lead_002",
      "from_email": "ops@betafreight.com",
      "subject": "Re: Cut Response Time by 60% — BetaFreight",
      "body": "Thanks for reaching out. What's the pricing for a team of 30?",
      "expected_classification": "Pricing Objection"
    },
    {
      "lead_id": "lead_003",
      "from_email": "tech@gammasupply.com",
      "subject": "Re: AI Customer Support — GammaSupply",
      "body": "Not interested at this time.",
      "expected_classification": "Not Interested"
    }
  ]

data/seeds/meetings_seed.json:
  [
    {
      "lead_id": "lead_001",
      "company_name": "AlphaLogistics",
      "contact_name": "Omar Al-Rashid",
      "contact_role": "CEO",
      "meeting_link": "https://cal.com/admin/alphalogistics",
      "scheduled_at": "2025-02-15T10:00:00Z",
      "briefing": {
        "customer_problem": "High volume of WhatsApp customer inquiries overwhelming 5-person support team",
        "recommended_service": "WhatsApp AI Chatbot with CRM Integration",
        "key_points": ["Ask about current response time SLA", "Mention 60% cost reduction case study"],
        "watch_out_for": ["Budget sign-off process", "IT approval for integrations"]
      }
    }
  ]
```

---

### STEP 9 — End-to-End Comms Test
**Prompt to give Claude Code:**
```
Create backend/test_comms.py — test script for the full comms layer.

1. Load data/seeds/replies_seed.json
2. For each reply:
   a. Call ResponseClassifier.classify() with the reply body
   b. Print: company, expected classification, actual classification, match: yes/no
3. Simulate a meeting request flow:
   a. Call MeetingManager.handle_meeting_request("lead_001")
   b. Print the returned meeting_link
   c. Print "WhatsApp sent: {bool}"
4. Test the follow-up scheduler logic:
   a. Print how many emails would qualify for follow-up if run right now (query DB)

Run the script and show output. Flag any errors.
```

---

## What You Depend On

- **Wajeeh** gives you: `backend/db/crud.py` with `create_email()`, `get_all_emails()`,
  `create_meeting()`, `get_all_meetings()`, `create_reply()`, `get_emails_needing_followup()`
  — coordinate with him on the exact function signatures before Step 4
- **Ismail** gives you: `backend/config/prompts.py` started — you add your own prompts to it

---

## Your Deliverable Checklist

- [ ] `backend/comms/email_sender.py` — sends real emails via Resend
- [ ] `backend/comms/response_classifier.py` — classifies all 9 categories correctly
- [ ] `backend/comms/followup_scheduler.py` — 3-day follow-up running via APScheduler
- [ ] `backend/comms/email_reader.py` — processes inbound webhook, matches to lead
- [ ] `backend/comms/meeting_manager.py` — generates link, sends email, triggers WhatsApp
- [ ] `backend/comms/whatsapp_notifier.py` — sends meeting confirmed + 30-min briefing
- [ ] `backend/api/routes/emails.py` — GET + POST working
- [ ] `backend/api/routes/meetings.py` — GET + POST working
- [ ] `backend/api/routes/webhook.py` — inbound reply webhook working
- [ ] `data/seeds/replies_seed.json` — 3 replies with correct classifications
- [ ] `data/seeds/meetings_seed.json` — 1 complete meeting with briefing
- [ ] `backend/test_comms.py` — runs clean with visible output
- [ ] `docs/api_reference.md` — you write the emails + meetings + webhook sections
