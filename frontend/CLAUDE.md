# Frontend — Working Rules

React 18 + Vite + TypeScript + Tailwind. Run it with:

```
cd frontend && npm install && npm run dev
```

## Non-negotiables

- **TypeScript everywhere. Never `any`.** Use `unknown` and narrow it.
- **All API calls go through `src/lib/api.ts`.** Never call axios or `fetch`
  from a component. New endpoint means a new function there first.
- **All types live in `src/lib/types.ts`.** Never declare a data shape inline.
  The types mirror `backend/api/schemas.py` — keep them in step.
- **Tailwind classes only.** No inline `style`, no CSS modules. Repeated
  patterns become a component, or a `@layer components` class in `index.css`.
- **Props are `interface`, not `type`.**
- **Component files are PascalCase, everything else camelCase.**
- **React Router v6** for navigation — `useNavigate`, not `window.location`.

## Design system

Warm terracotta, taken from the landing page (`src/styles/landing.css`) so the
app and the marketing page read as one product. Two custom scales in
`tailwind.config.ts` carry it:

- **`bark`** — the neutral. Replaces Tailwind's slate at the same scale
  positions: `bg-bark-900` page, `bg-bark-800` cards, `border-bark-700`,
  `bark-400`/`bark-500` for muted text. `bark-900` is the landing's `--frame`.
- **`terra`** — the accent. Replaces indigo. `terra-600` for primary actions
  (it clears AA on white text; `terra-500` does not, so don't swap it for
  label-bearing surfaces), `terra-400` for accent text and links.
- **`honey`** and **`cream`** for highlights and body text.

There is no slate or indigo left in `src/`. If you reach for one, you want
`bark` or `terra` instead.

Score colours always come from `scoreToColor()` / `scoreToBadgeColor()` in
`lib/utils.ts` — never hardcode a threshold, the bands must match everywhere.
`stageToColor()` is a deliberate heat ramp: cold `bark` for untouched leads,
warming through `honey` and `terra` as they engage, emerald once won, red when
dead. A new stage goes in its place on that gradient, not on a fresh hue.

Shared `@layer components` classes in `index.css`: `.card`,
`.card-interactive` (hover lift), `.input`, `.label`, `.text-ember` (the warm
display gradient — display type only, it is unreadable small), `.rule-ember`.

Shared atoms live in `components/ui/`: `Button`, `Badge`, `Modal`, `Spinner`,
`Toast`, `ProgressBar`, `EmptyState`. Reach for these before writing new markup.

## Data fetching

Pages use the hooks in `src/hooks/`:

- `usePipeline(sessionId)` — polls status every 3s while a run is live
- `useLeads(sessionId?)` — fetch, filter by stage, sort by score
- `useInbox()` — replies, auto-refreshing every 30s

Each returns `{ data, isLoading, error }`. Every page must render all three
states — a spinner while loading, the error message on failure, and
`<EmptyState />` when the result is empty. A blank screen is a bug.

Never swallow an error: pass it through `describeError()` from `lib/api.ts` and
show it in a `Toast` or inline.

## Routes

`/onboarding` and `/icp` are full-screen (no sidebar). `/pipeline`, `/leads`,
`/leads/:id`, `/inbox`, `/meetings` render inside the sidebar layout. `/`
redirects to `/onboarding`.

The active `session_id` is kept in localStorage via `saveSessionId()` /
`loadSessionId()` so a refresh mid-demo does not lose the run.

## Endpoints that may not exist yet

`POST /emails/send` and `POST /meetings/create` are Sufiyan's and may 404 on
some branches. Handle the failure with a toast — never let it throw into a
blank page.
