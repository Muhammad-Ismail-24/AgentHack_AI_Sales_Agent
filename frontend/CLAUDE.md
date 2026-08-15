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

Dark chrome: `bg-slate-900` page, `bg-slate-800` cards, `border-slate-700`,
indigo-500 for primary actions. Score colours always come from
`scoreToColor()` / `scoreToBadgeColor()` in `lib/utils.ts` — never hardcode a
threshold, the bands must match everywhere.

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
