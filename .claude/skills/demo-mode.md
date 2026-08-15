# Demo Mode

How to get the dashboard into a recordable state, and what to click.

## 1. Load the seed data

```bash
python backend/load_seeds.py
```

Expect: `Seed data loaded: 12 leads, 13 contacts, 7 emails, 3 replies, 1 meetings`

It wipes every table first, so it is always safe to re-run between takes. All
relative dates (`sent_days_ago`, meeting times) are resolved at load time, so
the data never looks stale no matter when you record.

Session id is `demo-session`.

## 2. Start the stack

```bash
docker-compose up --build
```

Or without Docker, in two terminals:

```bash
cd backend && uvicorn main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Check `http://localhost:8000/health` returns `{"status":"ok","database":"ok"}`
before recording. If `database` is not `ok`, the dashboard will be empty.

## 3. What the seed data contains

| Stage | Leads |
|---|---|
| Meeting Scheduled | AlphaLogistics (94) |
| Interested | BetaFreight (89), Gulfstream Retail (85) |
| Contacted | Emirates Cargo Link (92), SouqDirect (84), Desert Rose Trading (78) |
| Qualified | Falcon Freight (79), Marina Property (72), Oasis Distribution (65) |
| Researching | Levant Courier (unscored) |
| Not Interested | GammaSupply (71) |
| Not Qualified | Nile Textiles (34) |

Three replies are already classified: Meeting Requested (AlphaLogistics),
Pricing Objection (BetaFreight), Not Interested (GammaSupply). One meeting is
booked with a full briefing.

**Use AlphaLogistics (`lead_001`) for the meeting flow** — it is the only lead
with the complete chain: sent email → reply → classification → booked meeting
→ briefing.

## 4. Click order for the 1.5-minute video

1. **`/onboarding`** — drag in `data/seeds/company_sample.txt`, hit
   *Load company info*. Wait for the green "Company info loaded ✓". (2 shots)
2. **`/icp`** — fill in UAE / logistics and e-commerce / 51-200 /
   "drowning in WhatsApp customer inquiries". Hit *Start pipeline*.
3. **`/pipeline`** — land on the Kanban board. Pan across the columns so the
   stage counts and score badges are visible. Pause on Meeting Scheduled.
4. **Click AlphaLogistics** → lead detail. Show, in this order: the score 94
   with its explanation, the research summary, the generated email, then the
   timeline.
5. **`/inbox`** — three classified replies with colour-coded badges and a
   suggested next action under each.
6. **`/meetings`** — expand *Show pre-meeting briefing* on AlphaLogistics. End
   on the briefing: their problem, the pitch, key points, what to watch for.

That final briefing is the strongest single frame — hold it for the last
three seconds.

## 5. If the agent pipeline is not merged yet

`POST /pipeline/start` returns 503 when `backend/agents/orchestrator.py` is
absent, and the ICP page shows the message in a toast then moves on to the
dashboard after ~2.5s. The seeded board still demos in full. Either record
around it, or skip straight to `/pipeline` from the onboarding page's
"Skip to the dashboard" link.

## 6. Before you hit record

- Re-run `load_seeds.py` for a clean state.
- Hard-refresh the browser (localStorage keeps the last session id).
- Check `/health`, `/leads` returns 12, and `/inbox` returns 3.
- Zoom the browser to 100% — the Kanban board is sized for a 1280px viewport.
