# Demo Video Script (1 min 30 s)

Setup and seed data: see `.claude/skills/demo-mode.md`. Run
`python backend/load_seeds.py` immediately before recording.

Timings are targets, not a straitjacket — the last shot matters most, so
protect the final 15 seconds.

---

## 0:00 – 0:12 · The problem

**On screen:** `/onboarding`, empty.

> "Every sales team does the same four things by hand: find companies, research
> them, work out what to pitch, and write the email. We built an agent that
> does all four, then handles the reply."

## 0:12 – 0:28 · Onboarding

**Do:** drag `company_sample.txt` onto the drop zone. Click *Load company info*.
Wait for the green confirmation. Click *Continue*.

> "It starts by reading your company. This is NovaTech — what they sell, their
> pricing, their case studies. That goes into a vector store, and everything
> the agent pitches later comes out of it."

## 0:28 – 0:40 · ICP

**Do:** fill the four fields — UAE, logistics and e-commerce, 51-200,
"drowning in WhatsApp customer inquiries". Click *Start pipeline*.

> "Then you describe who you want. Location, industry, size, and the specific
> problem worth solving. That's the whole configuration."

## 0:40 – 0:58 · The pipeline

**On screen:** `/pipeline` Kanban board. Pan slowly left to right.

> "Nine agents run in sequence — discovery, filtering, deep research, scoring,
> service matching, decision-maker lookup, and email writing. Every lead lands
> in a stage with a score out of a hundred."

**Do:** pause on the Meeting Scheduled column. Click **AlphaLogistics**.

## 0:58 – 1:15 · One lead, end to end

**On screen:** `/leads/lead_001`.

**Do:** point at the score, scroll to the research summary, then the email.

> "Ninety-four. And it explains why: a hundred-and-eighty-person freight
> operator running support on WhatsApp, three open support roles, Salesforce
> already in the stack. The email quotes their own hiring page and a case study
> from a company down the road."

## 1:15 – 1:24 · The reply

**Do:** go to `/inbox`.

> "Replies come back classified. Interested, pricing objection, not interested
> — each with the next action already worked out. Silence gets a follow-up
> after three days, automatically."

## 1:24 – 1:30 · The close

**Do:** go to `/meetings`, expand *Show pre-meeting briefing*. Hold.

> "And when someone says yes, it books the meeting and writes the brief. Their
> problem, what to pitch, what to watch out for. You just show up."

---

## Shot notes

- Record at 1280×800. The Kanban board is laid out for that width.
- Hide bookmarks and any browser extensions.
- Do not narrate loading spinners — cut them.
- The final briefing frame is the money shot. Hold it for three full seconds
  after the voiceover ends.

## Code explanation video (1 min) — separate recording

1. `FOLDER_STRUCTURE.md` — three owners, clean boundaries (10 s)
2. `backend/agents/orchestrator.py` — the LangGraph state machine (20 s)
3. `backend/db/crud.py` — every query in one file, nothing raw anywhere (10 s)
4. `backend/comms/followup_scheduler.py` — APScheduler on a 3-day rule (10 s)
5. `frontend/src/lib/api.ts` + `types.ts` — one source of truth each (10 s)
