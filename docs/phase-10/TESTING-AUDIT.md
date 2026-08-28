# Phase 10 — Testing & Frontend Hardening Audit

## Backend test coverage

Already thoroughly inventoried in `docs/PHASE-9-AUDIT.md` (all 15 major
subsystems covered; skips are all environment-conditional, never a silent
`xfail`). As of the last full run (post Phase-9 P1 fixes): **702 backend
tests passing, 2 skipped**, ruff/mypy clean across all 5 Python packages.
Not re-derived here.

## Frontend production-hardening findings (new this pass)

1. **No React error boundary anywhere.** `main.tsx` mounts `<App>` inside
   `<StrictMode>` with no boundary in the tree. Any uncaught render
   exception (e.g. malformed API JSON causing `.map()` on `undefined`)
   unmounts the entire app to a blank white screen — no fallback UI.

2. **Loading vs. error vs. empty states are conflated.** `App.tsx` has a
   real top-level error banner (`role="alert"`) but no distinct loading
   state — `status` starts `null` and renders identically to "genuinely
   disconnected" until the first response arrives. `PlatformPanel.tsx`
   and `BrowserPanel.tsx`'s initial-load `refresh()` catch blocks are
   silent no-ops (comment: "leave the last-known lists in place") — a
   failed fetch is visually indistinguishable from a genuinely empty list,
   and "haven't loaded yet" is indistinguishable from "confirmed empty."

3. **A real, currently-possible stale-response race** in `App.tsx`'s 5s
   `/system` poll: no `AbortController`, no sequence number, no in-flight
   guard. If an older request resolves after a newer one, its `setStatus`
   call silently overwrites the newer state.

4. **Accessibility is minimal outside the avatar.** Only 3 total
   `aria-label`/`aria-live`/`role=`/`tabIndex` occurrences in the whole
   frontend, all in `Avatar.tsx`/`App.tsx`. `PlatformPanel.tsx`,
   `BrowserPanel.tsx`, `DevConsole.tsx` have none. On the positive side:
   every `onClick` in the codebase is on a native `<button>` — no
   keyboard-unreachable click-only `<div>` handlers exist anywhere.

5. **Cleanup is correct everywhere it matters for timers/sockets.**
   `App.tsx`'s poll interval and `useAvatarSocket.ts`'s reconnect + stale-
   watchdog timers (both fixed in Phase 9) are all properly cleared on
   unmount — no leak found there. The remaining minor issue:
   `PlatformPanel.tsx`/`BrowserPanel.tsx`/`DevConsole.tsx`'s mount-time
   fetches have no unmount guard, so React 18 StrictMode's dev
   double-invoke fires each GET twice on mount (harmless for idempotent
   reads, but real) and a fast unmount could `setState` after unmount
   (a React warning, not a hard leak).

## Priority for a follow-up frontend pass

An error boundary (item 1) is the highest-value single fix — it's the one
item that turns "a bug in one panel" into "the entire app going blank."
The stale-response race (item 3) is the next most concrete, since it can
silently show wrong system status. Loading/error/empty differentiation
(item 2) and accessibility (item 4) are real but lower urgency. None of
these were fixed in this audit pass — recorded here as prioritized
backlog for the next implementation pass, consistent with "audit first,
implement systematically after" per the Phase 10 brief.
