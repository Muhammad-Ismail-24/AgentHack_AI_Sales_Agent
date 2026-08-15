# Wajeeh — Work Breakdown (40%)
## Role: Backend Infrastructure + Full Frontend + Demo Lead

You have the largest share because you own two massive areas: the entire backend
infrastructure that both Ismail and Sufiyan's code *plugs into*, and the complete
frontend that judges will actually look at and interact with. You also lead the
demo preparation — the seed data, the demo script, and making sure everything
runs cleanly before recording.

Your work is the glue and the face of the project.

**Your folders:**
- `backend/db/` — full ownership
- `backend/memory/` — full ownership
- `backend/api/` (routes: company, icp, pipeline, leads) — full ownership
- `backend/api/schemas.py` — full ownership
- `backend/main.py` — full ownership
- `backend/CLAUDE.md` — you write it
- `frontend/` — full ownership of everything inside
- `data/seeds/` (leads, emails, company files) — you create these
- Root config files: `CLAUDE.md`, `.claudeignore`, `.claude/settings.json`,
  `.env.example`, `.gitignore`, `docker-compose.yml`, `README.md`

---

## What You Are Building — Full Description

### 1. Project Bootstrap & Root Config Files
You set up the entire project structure on day one. You create the GitHub repo,
the root CLAUDE.md, the .claudeignore, the docker-compose.yml, the .env.example,
and the .gitignore. This is the first thing you do so Ismail and Sufiyan can clone
and start immediately.

### 2. Database Layer (The Most Critical Backend Piece)
Both Ismail's agents and Sufiyan's comms layer read and write to the database.
You define the schema, create all SQLAlchemy models, write all migrations, and
— most importantly — write all CRUD functions in `crud.py`. Ismail and Sufiyan
never write raw DB queries. They only call functions from your `crud.py`.

Tables you own: Lead, Contact, Email, Reply, Meeting, FollowUp, PipelineEvent.
Every column, every relationship, every index. Get this right early because
changing the schema later breaks everyone.

### 3. Memory Layer
Short-term memory (Redis) stores the active pipeline state during a run — which
stage it's on, any errors, the current session context. Long-term memory is a
clean interface over the database that lets any part of the system say
"remember this about lead X" or "what do we know about company Y" without
writing SQL.

### 4. FastAPI App Entry + Shared Routes
You write `backend/main.py` which registers all routers from all three teammates.
You also write the four routes that are yours:
- `POST /company/upload` and `POST /company/text` — receive company info, trigger RAG
- `POST /icp/define` — receive ICP form input, kick off the pipeline
- `POST /pipeline/start` and `GET /pipeline/status/{id}` — start the full pipeline run and poll status
- `GET /leads`, `GET /leads/{id}`, `PATCH /leads/{id}` — leads CRUD for the frontend

### 5. Full Frontend (React + Vite + TypeScript + Tailwind)
This is what judges interact with and what the demo video shows. You build:
- Onboarding flow (upload PDF or paste text, define ICP)
- Pipeline Kanban board showing all leads by stage
- Lead detail page (score, research, email preview, contacts)
- Inbox page (replies with classification badges)
- Meetings page (upcoming meetings with briefings)
- All shared UI components (Button, Badge, Modal, Spinner, Toast)
- The API layer (`lib/api.ts`) and all TypeScript types (`lib/types.ts`)

The frontend must look clean and professional. Judges score it at 15% of total.
Use a dark sidebar layout, clear typography, and colour-coded score badges.

### 6. Demo Seed Data & Demo Leadership
You prepare all seed data for the demo video:
- A real company sample PDF and text file
- Pre-researched leads with scores
- Pre-generated emails ready to send
- The demo script that all three of you follow when recording

---

## Steps for Claude Code to Follow

These steps are ordered. Steps 1–3 must be done **first, on day one**, because
Ismail and Sufiyan are blocked without the project structure and DB layer.

---

### STEP 1 — Project Root Setup (Day 1 — Do This First)
**Prompt to give Claude Code:**
```
Set up the entire project root structure. Create all of these files:

1. CLAUDE.md — master instructions file. Include:
   - One-line project description
   - Tech stack table (React+Vite frontend, Python FastAPI backend, LangGraph, Qdrant, Supabase, Redis)
   - Key commands: cd backend && uvicorn main:app --reload, cd frontend && npm run dev, docker-compose up
   - Architecture rule: all prompts in backend/config/prompts.py
   - Architecture rule: all TypeScript types in frontend/src/lib/types.ts
   - Architecture rule: all frontend API calls through frontend/src/lib/api.ts
   - Architecture rule: all DB queries through backend/db/crud.py
   - DO NOTs: never commit .env, never use print() in backend, never fetch from components directly

2. .claudeignore — patterns to exclude:
   node_modules/, .venv/, __pycache__/, *.pyc, dist/, build/,
   .env, .env.*, *.pem, *.key, data/uploads/, data/cache/, data/seeds/*.pdf,
   *.log, *.tmp, .DS_Store, backend/db/migrations/versions/,
   package-lock.json, yarn.lock, poetry.lock

3. .claude/settings.json — project permissions:
   allow: git log, git diff, git status, git add, git commit, git branch,
          pip install *, npm install *, npm run dev, npm run build,
          uvicorn *, python *, alembic *
   deny: Read(.env), Read(.env.*), Bash(rm -rf *), Bash(sudo *)
   model: claude-sonnet-4-6

4. .gitignore:
   .env, .env.*, .venv/, __pycache__/, *.pyc, node_modules/,
   dist/, build/, *.egg-info/, data/uploads/, data/cache/,
   .claude/settings.local.json, *.log, .DS_Store

5. .env.example — every key the project needs, with empty values:
   ANTHROPIC_API_KEY=
   TAVILY_API_KEY=
   SERPER_API_KEY=
   APOLLO_API_KEY=
   HUNTER_API_KEY=
   QDRANT_URL=
   QDRANT_API_KEY=
   REDIS_URL=
   DATABASE_URL=
   RESEND_API_KEY=
   SENDER_EMAIL=
   TWILIO_ACCOUNT_SID=
   TWILIO_AUTH_TOKEN=
   TWILIO_WHATSAPP_FROM=
   ADMIN_WHATSAPP_NUMBER=
   CALCOM_API_KEY=
   VITE_API_URL=http://localhost:8000

6. README.md — include:
   - Project title and one-paragraph description
   - Prerequisites (Python 3.11, Node 18+, Docker)
   - Setup steps: clone repo, copy .env.example to .env, fill in keys,
     docker-compose up --build, open http://localhost:5173
   - Architecture overview (brief)

7. Create all empty directories with .gitkeep:
   data/uploads/.gitkeep
   data/cache/.gitkeep
   data/seeds/.gitkeep
   docs/.gitkeep
   backend/agents/.gitkeep
   backend/comms/.gitkeep
   backend/rag/.gitkeep
   backend/tools/.gitkeep
   backend/memory/.gitkeep
   backend/db/migrations/versions/.gitkeep
   backend/api/routes/.gitkeep
   backend/config/.gitkeep
   backend/utils/.gitkeep

After creating everything: git init, git add ., git commit -m "chore: project structure"
```

---

### STEP 2 — Database Models & Migrations (Do Before Telling Ismail/Sufiyan to Start)
**Prompt to give Claude Code:**
```
Set up the full database layer in backend/db/.

Install: pip install sqlalchemy alembic psycopg2-binary

1. backend/db/__init__.py (empty)

2. backend/db/database.py:
   - Create SQLAlchemy async engine from DATABASE_URL in settings
   - Create async SessionLocal
   - Expose: get_db() dependency for FastAPI routes
   - Expose: Base = declarative_base()

3. backend/db/models.py — all SQLAlchemy models:

   class Lead(Base):
     id (UUID, primary key, default uuid4)
     company_name (String, not null)
     website (String)
     industry (String)
     location (String)
     employee_count (Integer)
     pipeline_stage (String, default "Discovered")
       # Stages: Discovered, Potential, Researching, Qualified,
       # Contacted, Interested, Meeting Scheduled, Converted,
       # Not Qualified, Not Interested, Do Not Contact
     lead_score (Integer)
     score_explanation (Text)
     recommended_service (String)
     pitch_angle (Text)
     icp_fit (Boolean)
     research_summary (Text)
     apollo_data (JSON)
     session_id (String)
     created_at (DateTime, default now)
     updated_at (DateTime, onupdate now)

   class Contact(Base):
     id (UUID, primary key)
     lead_id (UUID, FK leads.id, cascade delete)
     name (String)
     role (String)
     email (String)
     linkedin_url (String)
     is_primary (Boolean, default False)

   class Email(Base):
     id (UUID, primary key)
     lead_id (UUID, FK leads.id)
     contact_id (UUID, FK contacts.id)
     subject (String)
     body (Text)
     status (String, default "draft") # draft, sent, failed, replied
     sent_at (DateTime)
     created_at (DateTime, default now)

   class Reply(Base):
     id (UUID, primary key)
     email_id (UUID, FK emails.id)
     raw_body (Text)
     classification (String)
     summary (Text)
     next_action (String)
     received_at (DateTime)

   class Meeting(Base):
     id (UUID, primary key)
     lead_id (UUID, FK leads.id)
     contact_id (UUID, FK contacts.id)
     meeting_link (String)
     scheduled_at (DateTime)
     briefing (JSON)
     admin_notified (Boolean, default False)
     status (String, default "link_sent") # link_sent, confirmed, completed, cancelled
     created_at (DateTime, default now)

   class FollowUp(Base):
     id (UUID, primary key)
     lead_id (UUID, FK leads.id)
     original_email_id (UUID, FK emails.id)
     followup_email_id (UUID, FK emails.id, nullable)
     scheduled_for (DateTime)
     status (String, default "pending") # pending, sent, cancelled
     created_at (DateTime, default now)

   class PipelineEvent(Base):
     id (UUID, primary key)
     lead_id (UUID, FK leads.id)
     from_stage (String)
     to_stage (String)
     reason (String)
     created_at (DateTime, default now)

4. backend/db/migrations/ — set up Alembic:
   Run: alembic init backend/db/migrations
   Edit alembic.ini to use DATABASE_URL from settings
   Edit migrations/env.py to import Base from models
   Run: alembic revision --autogenerate -m "initial schema"
   Run: alembic upgrade head

5. Update .claude/skills/database-schema.md with every table and column listed above
```

---

### STEP 3 — CRUD Functions
**Prompt to give Claude Code:**
```
Build backend/db/crud.py with ALL database operations.
Import AsyncSession. Every function is async. Group by entity.

LEADS:
  create_lead(db, lead_dict) -> Lead
  get_lead(db, lead_id) -> Lead | None
  get_all_leads(db, session_id=None) -> list[Lead]
  update_lead_stage(db, lead_id, new_stage, reason) -> Lead
    (also creates a PipelineEvent entry)
  update_lead_score(db, lead_id, score, explanation) -> Lead
  update_lead_research(db, lead_id, research_summary, apollo_data) -> Lead
  update_lead_service(db, lead_id, recommended_service, pitch_angle) -> Lead
  upsert_leads_from_pipeline(db, leads_list, session_id) -> list[Lead]
    (bulk create/update from the pipeline state outreach_queue)

CONTACTS:
  create_contact(db, contact_dict, lead_id) -> Contact
  get_contacts_for_lead(db, lead_id) -> list[Contact]
  get_primary_contact(db, lead_id) -> Contact | None

EMAILS:
  create_email(db, lead_id, contact_id, subject, body, status) -> Email
  get_all_emails(db) -> list[Email]
  get_emails_for_lead(db, lead_id) -> list[Email]
  get_emails_needing_followup(db) -> list[Email]
    (sent > 3 days ago, no reply, no followup sent yet)
  update_email_status(db, email_id, status) -> Email

REPLIES:
  create_reply(db, email_id, raw_body, classification, summary, next_action) -> Reply
  get_replies_for_lead(db, lead_id) -> list[Reply]

MEETINGS:
  create_meeting(db, lead_id, contact_id, meeting_link, scheduled_at) -> Meeting
  get_all_meetings(db) -> list[Meeting]
  get_upcoming_meetings_needing_reminder(db) -> list[Meeting]
    (scheduled within next 35 minutes, admin_notified == False)
  update_meeting_admin_notified(db, meeting_id) -> Meeting
  update_meeting_briefing(db, meeting_id, briefing_dict) -> Meeting

FOLLOWUPS:
  create_followup(db, lead_id, original_email_id, scheduled_for) -> FollowUp
  update_followup_sent(db, followup_id, followup_email_id) -> FollowUp

PIPELINE EVENTS:
  get_events_for_lead(db, lead_id) -> list[PipelineEvent]
```

---

### STEP 4 — Memory Layer
**Prompt to give Claude Code:**
```
Build backend/memory/short_term.py and backend/memory/long_term.py

backend/memory/short_term.py:
  Uses Redis (import from utils/cache.py pattern)
  class ShortTermMemory:
    set_pipeline_state(session_id: str, state: dict) -> None
      - Serialize state to JSON, store in Redis key "pipeline:{session_id}"
      - TTL: 2 hours
    get_pipeline_state(session_id: str) -> dict | None
      - Deserialize from Redis, return None if not found
    set_pipeline_stage(session_id: str, stage: str) -> None
      - Store in Redis key "stage:{session_id}"
    get_pipeline_stage(session_id: str) -> str | None
    clear_session(session_id: str) -> None
      - Delete "pipeline:{session_id}" and "stage:{session_id}"

backend/memory/long_term.py:
  Thin wrapper over crud.py with natural-language-ish method names
  class LongTermMemory:
    async remember_lead(db, lead_dict, session_id) -> Lead
      - Calls crud.upsert_leads_from_pipeline
    async remember_contact(db, contact_dict, lead_id) -> Contact
      - Calls crud.create_contact
    async recall_lead_history(db, lead_id) -> dict
      - Returns: {lead, contacts, emails, replies, meetings, events}
      - Assembles a complete history dict for a lead
    async what_stage_is(db, lead_id) -> str
      - Returns current pipeline_stage of the lead
```

---

### STEP 5 — FastAPI App + Remaining Routes
**Prompt to give Claude Code:**
```
Build backend/main.py and the 4 API route files you own.

backend/api/schemas.py — Pydantic models for all requests + responses:
  CompanyUploadResponse, ICPRequest, ICPResponse,
  PipelineStartRequest, PipelineStatusResponse,
  LeadResponse (all lead fields), LeadUpdateRequest,
  ContactResponse, EmailResponse, MeetingResponse, ReplyResponse

backend/main.py:
  - Create FastAPI app
  - Add CORS middleware (allow all origins for hackathon)
  - Include all routers (yours + Ismail's + Sufiyan's):
      /company, /icp, /pipeline, /leads, /emails, /meetings, /webhook
  - On startup: init DB tables, start APScheduler from comms.followup_scheduler
  - GET /health — returns {status: "ok"}

backend/api/routes/company.py:
  POST /company/upload
    - Accept file upload (UploadFile)
    - Save to data/uploads/
    - Call orchestrator's RAG ingest function with the filepath
    - Return {session_id, company_name, status: "ingested"}
  POST /company/text
    - Body: {text: str}
    - Call orchestrator's RAG ingest function with the text
    - Return {session_id, company_name, status: "ingested"}

backend/api/routes/icp.py:
  POST /icp/define
    - Body: ICPRequest {session_id, location, industry, company_size, special_focus}
    - Store ICP in ShortTermMemory for the session
    - Return {session_id, icp: structured_icp_dict}

backend/api/routes/pipeline.py:
  POST /pipeline/start
    - Body: {session_id}
    - Retrieve company + ICP from ShortTermMemory
    - Call orchestrator.run_pipeline() in background (asyncio task)
    - Return {session_id, status: "running"}
  GET /pipeline/status/{session_id}
    - Get current stage from ShortTermMemory
    - Get lead counts from DB for this session
    - Return {stage, raw_leads_count, filtered_count, qualified_count, outreach_count}

backend/api/routes/leads.py:
  GET /leads
    - Query param: session_id (optional)
    - Returns all leads (or leads for session)
    - Each lead includes contacts list
  GET /leads/{lead_id}
    - Full lead detail: lead + contacts + emails + replies + meetings + events
    - Calls long_term_memory.recall_lead_history()
  PATCH /leads/{lead_id}
    - Body: {pipeline_stage}
    - Manually move a lead to a new stage (with "manual" reason)
    - Returns updated lead
```

---

### STEP 6 — Backend CLAUDE.md & Skill Files
**Prompt to give Claude Code:**
```
Create backend/CLAUDE.md with instructions for working in the backend:
  - FastAPI patterns: always use async def for route handlers
  - All DB calls must go through backend/db/crud.py — no raw SQL anywhere
  - All prompts in backend/config/prompts.py — never inline
  - Use backend/utils/logger.py — never print()
  - Routes return Pydantic schemas — never raw dicts
  - Error handling: use HTTPException with appropriate status codes
  - File structure: one router per domain (company, icp, pipeline, leads, emails, meetings, webhook)

Create .claude/skills/api-contracts.md at project root:
  Document every endpoint:
  Method, Path, Request body shape, Response shape, Which file handles it, Who owns it
  Include all routes from all three teammates.

Create .claude/skills/database-schema.md at project root:
  Full table and column list (copy from db/models.py)
  Foreign key relationships
  Enum values for pipeline_stage and status fields
```

---

### STEP 7 — Frontend Bootstrap
**Prompt to give Claude Code:**
```
Scaffold the full React + Vite + TypeScript + Tailwind frontend.

cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install react-router-dom axios react-dropzone

Configure tailwind.config.ts to scan src/**/*.{ts,tsx}
Add tailwind directives to src/index.css

Set up vite.config.ts with API proxy:
  server: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: path => path.replace(/^\/api/, '') } } }

Create frontend/CLAUDE.md:
  - Always use TypeScript, never any
  - All API calls go through src/lib/api.ts — never fetch from components
  - All types defined in src/lib/types.ts — never define inline
  - Use Tailwind classes only — no inline styles
  - Component files: PascalCase. Utility files: camelCase
  - Props must be typed with interfaces, not type aliases
  - Use React Router v6 for navigation

Create src/lib/types.ts with all TypeScript interfaces:
  Lead, Contact, Email, Reply, Meeting, FollowUp,
  PipelineEvent, ICP, PipelineStatus, ClassificationBadge
  Match every field to the DB schema exactly.

Create src/lib/api.ts with all API call functions:
  uploadCompanyPDF(file: File) -> Promise<{session_id, company_name}>
  submitCompanyText(text: string) -> Promise<{session_id, company_name}>
  defineICP(params) -> Promise<{session_id, icp}>
  startPipeline(session_id) -> Promise<{status}>
  getPipelineStatus(session_id) -> Promise<PipelineStatus>
  getLeads(session_id?) -> Promise<Lead[]>
  getLeadDetail(lead_id) -> Promise<LeadDetail>
  updateLeadStage(lead_id, stage) -> Promise<Lead>
  getEmails() -> Promise<Email[]>
  sendEmail(lead_id, contact_id, subject, body) -> Promise<{success}>
  getMeetings() -> Promise<Meeting[]>
  createMeeting(lead_id) -> Promise<{meeting_link}>

Create src/lib/utils.ts:
  scoreToColor(score: number) -> string  (returns Tailwind text colour class)
    0-40: text-red-500, 41-65: text-yellow-500, 66-80: text-blue-500, 81-100: text-green-500
  stageToColor(stage: string) -> string  (returns Tailwind bg colour class)
  formatDate(iso: string) -> string  (returns "15 Feb 2025, 10:00")
  truncate(text: string, n: number) -> string
```

---

### STEP 8 — Shared UI Components
**Prompt to give Claude Code:**
```
Build all shared UI components in frontend/src/components/ui/

Design system: dark background (#0f172a slate-900), white text,
accent colour indigo-500 for primary actions, score badges use utils.scoreToColor.

1. Button.tsx
   Props: children, onClick, variant ("primary"|"secondary"|"ghost"|"danger"),
          size ("sm"|"md"|"lg"), disabled, loading
   Loading state shows a spinner inside the button

2. Badge.tsx
   Props: label, color ("green"|"yellow"|"red"|"blue"|"gray"|"indigo")
   Small pill badge, solid colour background

3. Modal.tsx
   Props: isOpen, onClose, title, children
   Overlay background, centered white card, close button top-right

4. Spinner.tsx
   Props: size ("sm"|"md"|"lg"), color
   Tailwind animate-spin circle

5. Toast.tsx
   Props: message, type ("success"|"error"|"info"), onClose
   Fixed bottom-right, auto-dismiss after 3s

6. ProgressBar.tsx
   Props: label, current, total
   Shows "Researching leads... 4 of 12" with animated progress bar

7. EmptyState.tsx
   Props: title, description, actionLabel, onAction
   Centred empty state with icon placeholder and CTA button

Build the layout components:
8. components/layout/Sidebar.tsx
   Fixed left sidebar, dark background
   Nav items: Pipeline, Leads, Inbox, Meetings
   Show active item with indigo left border
   Show pipeline run status indicator at bottom (dot: green=running, grey=idle)

9. components/layout/TopBar.tsx
   Page title on left, pipeline status text on right
   "Pipeline running..." with spinner when active, "Idle" when not

10. components/layout/PageWrapper.tsx
    Wraps all page content with consistent padding and max-width
```

---

### STEP 9 — Frontend Pages
**Prompt to give Claude Code:**
```
Build all 6 pages in frontend/src/pages/

1. Onboarding.tsx
   Two tabs: "Upload PDF" and "Paste Text"
   Upload tab: drag-and-drop zone (react-dropzone), shows filename when file selected
   Text tab: large textarea for pasting company description
   Below both: "Company info loaded ✓" confirmation when submitted
   Large "Continue →" button goes to /icp

2. ICP.tsx
   Form with 4 fields:
   - Target Location (text input)
   - Target Industry (text input)
   - Company Size (dropdown: 1-10, 11-50, 51-200, 201-1000, 1000+)
   - Special Focus (textarea: what problem or use case to target)
   "Start Pipeline" button → calls startPipeline() → navigates to /pipeline

3. Pipeline.tsx (the main page)
   Kanban board with 8 columns:
   Discovered | Potential | Researching | Qualified | Contacted | Interested | Meeting Scheduled | Converted
   Also show a "Rejected" section below for: Not Qualified, Not Interested, Do Not Contact
   
   Each column shows a count badge
   Pipeline status bar at top: "Pipeline running — Researching leads (stage 5 of 9)"
   ProgressBar component shows live status (poll GET /pipeline/status every 3s while running)
   
   LeadCard per lead — show: company name, score badge, industry, location
   Clicking a card navigates to /leads/{id}

4. Leads.tsx
   Table view of all leads with columns:
   Company | Industry | Location | Score | Stage | Recommended Service | Contacts | Actions
   Filter bar: search by company name, filter by stage, sort by score
   Score shown as coloured badge using scoreToColor utility
   "View Details" button per row → /leads/{id}

5. LeadDetail.tsx
   Left column (60%): Research Summary accordion, Generated Email card, Timeline of events
   Right column (40%): Lead score big number with explanation, Contact cards, Recommended service

   Research Summary: expandable section showing what was found (website, Apollo data, news)
   Email card: shows subject + body, "Send Email" button → calls sendEmail()
   Timeline: list of PipelineEvents showing stage transitions with timestamps
   Contact cards: each contact with name, role, email, LinkedIn — "Primary" badge on main contact
   Score: big number (e.g. "87") with colour, below it the score_explanation text

6. Inbox.tsx
   List of all email replies, newest first
   Each reply: company name, contact name, classification badge, summary, received time
   Classification badge colours: Interested=green, Pricing Objection=yellow,
   Not Interested=red, Meeting Requested=indigo
   Below each reply: "Next Action" label showing suggested_next_action from classifier

7. Meetings.tsx
   List of all meetings
   Each meeting: company name, contact, scheduled time, meeting link button
   Briefing section per meeting: collapsible, shows customer_problem, recommended_service,
   key_points as bullets, watch_out_for as bullets
   "Join Meeting" button opens meeting_link in new tab
```

---

### STEP 10 — Custom Hooks
**Prompt to give Claude Code:**
```
Build the three custom hooks in frontend/src/hooks/

1. usePipeline.ts
   Takes session_id as arg
   Calls getPipelineStatus() every 3 seconds while status.stage is not "complete" or "idle"
   Returns {status, isRunning, error}
   Cleans up interval on unmount

2. useLeads.ts
   Calls getLeads() on mount
   Returns {leads, isLoading, error, refetch}
   Exposes filterByStage(stage) -> Lead[]
   Exposes sortByScore() -> Lead[]

3. useInbox.ts
   Calls getEmails() on mount
   Filters emails where status == "replied" and joins with replies data
   Auto-refreshes every 30 seconds
   Returns {replies, isLoading, error}

Wire up App.tsx with React Router:
  / → redirect to /onboarding
  /onboarding → Onboarding page
  /icp → ICP page
  /pipeline → Pipeline page (with sidebar layout)
  /leads → Leads page (with sidebar layout)
  /leads/:id → LeadDetail page (with sidebar layout)
  /inbox → Inbox page (with sidebar layout)
  /meetings → Meetings page (with sidebar layout)

Pages after /onboarding and /icp use the sidebar layout.
Pages /onboarding and /icp are full-screen (no sidebar).
```

---

### STEP 11 — Demo Seed Data
**Prompt to give Claude Code:**
```
Create all seed files in data/seeds/ for the demo video.

data/seeds/company_sample.txt:
  Write a realistic company description for "NovaTech Solutions" — a Pakistan-based
  AI software company that builds:
  1. WhatsApp AI Chatbots for customer support automation
  2. CRM Integration tools connecting WhatsApp to Salesforce/HubSpot
  3. AI Email Assistant for sales teams
  4. Custom LLM solutions for enterprise

  Include: services with pricing, case studies (2), target industries (logistics, e-commerce, real estate),
  technologies used, team size (25 people), founded 2022, offices in Karachi and Dubai.

data/seeds/icp_seed.json:
  {
    "location": "UAE",
    "industry": "logistics and e-commerce",
    "company_size": "50-500",
    "special_focus": "companies drowning in WhatsApp customer inquiries"
  }

data/seeds/leads_seed.json:
  Create 12 realistic leads with all fields populated:
  3 leads in "Contacted" stage with scores 78-92
  2 leads in "Interested" stage with scores 85-91
  1 lead in "Meeting Scheduled" stage with score 94
  3 leads in "Qualified" stage with scores 65-79
  2 leads in "Not Qualified" stage with scores 28-35
  1 lead in "Researching" stage

  For each lead include: company_name, website, industry, location, employee_count,
  pipeline_stage, lead_score, score_explanation, recommended_service, research_summary,
  and at least 1 contact with name + role + email

data/seeds/emails_seed.json:
  Pre-generated outreach emails for the 3 "Contacted" leads.
  Each email: subject (personalised), body (150 words, evidence-based, role-specific),
  status "sent", sent_at 3 days ago

Create .claude/skills/demo-mode.md:
  Instructions for running the demo:
  1. How to load seed data into the DB (python backend/load_seeds.py)
  2. The exact click order for the 1.5-minute demo video
  3. Which lead to use for the meeting flow demo
  4. What reply email to send manually before recording

Also create backend/load_seeds.py:
  Script that reads all seed JSON files and inserts them into the DB
  Clears existing data first (dev only)
  Prints "Seed data loaded: X leads, Y emails, Z meetings"
```

---

### STEP 12 — Docker & Final Integration
**Prompt to give Claude Code:**
```
Create docker-compose.yml that runs the full stack:

services:
  backend:
    build: ./backend
    ports: 8000:8000
    env_file: .env
    depends_on: [db, redis, qdrant]

  frontend:
    build: ./frontend
    ports: 5173:5173
    environment:
      VITE_API_URL: http://backend:8000

  db:
    image: postgres:15
    environment: POSTGRES_DB=agenthack, POSTGRES_USER=admin, POSTGRES_PASSWORD=password
    ports: 5432:5432
    volumes: postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports: 6379:6379

  qdrant:
    image: qdrant/qdrant
    ports: 6333:6333
    volumes: qdrant_storage:/qdrant/storage

volumes: postgres_data, qdrant_storage

Create backend/Dockerfile:
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  RUN playwright install chromium
  COPY . .
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

Create frontend/Dockerfile:
  FROM node:18-alpine
  WORKDIR /app
  COPY package*.json .
  RUN npm install
  COPY . .
  EXPOSE 5173
  CMD ["npm", "run", "dev", "--", "--host"]

Test: docker-compose up --build
Confirm frontend loads at localhost:5173 and backend /health returns 200.
```

---

## What You Give to Ismail and Sufiyan (Before They Can Start)

These are blocking dependencies — finish them **first**:

For **Ismail**: Give him `backend/db/models.py`, `backend/db/crud.py`, and
`backend/utils/logger.py` and `backend/utils/cache.py` before he starts Step 3.

For **Sufiyan**: Give him the full `crud.py` with `create_email()`,
`get_emails_needing_followup()`, `create_meeting()`, `create_reply()` —
these are blocking for his Steps 4 and 5. Also confirm the exact field names.

Share `frontend/src/lib/types.ts` with Sufiyan as soon as it's written
so he knows the shape of the data coming back from his routes.

---

## Your Deliverable Checklist

- [ ] Root config files: CLAUDE.md, .claudeignore, .claude/settings.json, .env.example, .gitignore, README.md
- [ ] `backend/db/models.py` — all 7 tables with correct columns
- [ ] `backend/db/database.py` — async SQLAlchemy connection working
- [ ] `backend/db/crud.py` — all CRUD functions for all tables
- [ ] `backend/db/migrations/` — Alembic set up, initial migration applied
- [ ] `backend/memory/short_term.py` — Redis pipeline state
- [ ] `backend/memory/long_term.py` — lead history interface
- [ ] `backend/api/schemas.py` — all Pydantic schemas
- [ ] `backend/api/routes/company.py` — upload + text routes
- [ ] `backend/api/routes/icp.py` — ICP definition route
- [ ] `backend/api/routes/pipeline.py` — start + status routes
- [ ] `backend/api/routes/leads.py` — list + detail + patch routes
- [ ] `backend/main.py` — all routers registered, startup events
- [ ] `backend/CLAUDE.md` — written and committed
- [ ] `docker-compose.yml` — full stack spins up cleanly
- [ ] `frontend/` — all pages, components, hooks working
- [ ] `data/seeds/` — company text, ICP, 12 leads, emails all present
- [ ] `backend/load_seeds.py` — seeds load into DB cleanly
- [ ] `.claude/skills/api-contracts.md` — every endpoint documented
- [ ] `.claude/skills/demo-mode.md` — demo script written
- [ ] `docs/demo_script.md` — click-by-click demo video script
- [ ] Final integration test: docker-compose up, load seeds, walk through full demo
