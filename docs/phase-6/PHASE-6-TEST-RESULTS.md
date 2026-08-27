# Phase 6 Test Results

Run in this environment (Linux container, no audio hardware, real
SQLite, real HTTP via `httpx.AsyncClient`, real Chromium via Playwright
for the frontend), 2026-08-27.

## 1. Summary

- **Full backend suite**: 460 passed, 0 failed, 2 skipped (pre-existing
  Phase 2 Windows-only skips, unrelated to this phase) —
  `scripts/check-python.sh`.
- **New backend tests this phase**: 32 (`test_avatar_mapping.py` 16,
  `test_voice_visemes.py` 11, `test_avatar_ui_state.py` 5), plus 2
  pre-existing `test_voice_events.py` assertions updated (not added) now
  that `voice.ui_state.changed` genuinely fires.
- **Lint/types**: `ruff check` clean across all five Python packages and
  `tests/`; `mypy` clean — `veyra_contracts` (12 files), `computer_control`
  (25), `vision` (19), `veyra-voice` (20), `app` (77).
- **Frontend**: `apps/desktop` gained a test runner this phase (none
  existed before) — 53 `vitest` tests, all passing; `tsc -b` clean;
  `eslint .` clean; `vite build` succeeds.

## 2. What was verified for real vs. reviewed-only vs. not shipped

| Area | Status |
|---|---|
| `compute_agent_state_from_task` | **Real** — exhaustive over every `TaskState`, pure function, unit-tested |
| `text_to_visemes` | **Real** — deterministic, stdlib-only, unit-tested; see `LIP-SYNC.md` for what "real" means here |
| `voice.ui_state.changed` publishing | **Real** — genuinely fires at 5 distinct real transition points in `VoiceConversationManager`, verified end-to-end against the real `event_bus` |
| TypeScript contracts (`TaskState`, `EventType`, `AgentState`, `Event`) | **Real** — corrected to match the Python source of truth, `tsc` clean |
| `/events` WebSocket consumption | **Real** — `useAvatarSocket` connects to the actual Phase 1 endpoint; verified in a real browser (Chromium) against the real `vite` dev build with simulated real-shaped frames |
| Avatar rendering (aura, eyes, eyebrows, mouth) | **Real** — SVG driven entirely by `AgentState`/viseme data via a pure, tested reducer; visually confirmed in-browser across LISTENING/THINKING/SPEAKING(SUCCESS)/SPEAKING(ERROR)/CONFIRMING |
| Audio-driven or facial-capture-driven lip sync | **Not shipped** — no audio hardware/library/model exists in this environment (unchanged from Phase 5); `text_to_visemes` is the honestly-scoped substitute, see `LIP-SYNC.md` |
| Granular in-task-step avatar reactions during a voice turn | **Not attempted** — architectural scoping choice, see `AVATAR-ARCHITECTURE.md` §6 |
| Real Tauri desktop window rendering the avatar | **Reviewed only** — the React component tree is exercised in a real browser via `vite`'s dev server (Tauri wraps the same web build); no Tauri-specific rendering difference is expected, but the actual `.exe`/window chrome isn't buildable/runnable in this Linux container (same category as Phase 2's Windows-only gap) |

## 3. Real bugs found and fixed during this phase's own verification

1. **The TypeScript contracts package had silently drifted from Python.**
   `packages/contracts/typescript/src/enums.ts` still had Phase 1's
   original `TaskState` (missing `PAUSED`, `TIMED_OUT`), Phase 1's
   original `EventType` (missing every Phase 4/5 addition — `task.created`
   through `voice.ui_state.changed`), and a `AvatarState` type whose
   *values* didn't match `AgentState` at all (`WAITING_CONFIRMATION`
   instead of `CONFIRMING`, a `WARNING` value Python never had, missing
   `UNDERSTANDING`/`PLANNING`/`WAITING`/`RECOVERING`/`PAUSED`), despite the
   file's own header comment: "Mirrors ...enums.py — keep in sync."
   Nothing had caught this because nothing in the desktop app consumed
   any of these types yet. Fixed by rewriting all three to match Python
   exactly and renaming `AvatarState` to `AgentState` to match the
   contract it always meant to mirror.
2. **`ruff`'s `E741` flagged `VisemeShape.O`** (ambiguous with the digit
   `0`) before this ever reached CI — renamed to `OH` in both the Python
   enum and the TypeScript mirror before it became a real inconsistency
   between a merged name and a lint suppression.

Neither is a functional regression in shipped behavior (the stale TS
contracts were unused dead weight, not a bug a user could hit) but both
are exactly the kind of drift CLAUDE.md's documentation-consistency rule
("When code and docs disagree, that is a bug — fix whichever is wrong")
extends to code-vs-code drift between mirrored contract packages.

## 4. Known limitations

- **No real TTS audio, wake-word, or STT model** — unchanged from Phase
  5; lip sync is text-driven, not audio-driven (`LIP-SYNC.md`).
- **No granular avatar reaction to individual task steps during a voice
  turn** — the avatar shows one "THINKING" state for the whole bundled
  transcribe/understand/plan/execute/recover phase of a voice turn, the
  same synchronous-turn boundary `BARGE-IN.md` §5 already documents for
  `PAUSE_TASK` (`AVATAR-ARCHITECTURE.md` §6).
- **No real Tauri window was built/run** — this Linux container cannot
  produce a Windows `.exe`; the React/SVG avatar itself was verified in a
  real Chromium browser against the same web build Tauri wraps.
- **Visual design is intentionally modest** — an original, abstract SVG
  presence (aura + simple facial features), not photorealistic rendering,
  per the product brief's own Phase 1 note ("do not spend excessive time
  on visual design") carried forward in spirit even though Phase 6 is
  explicitly the phase that ships the "final" identity; further visual
  polish (more expressions, smoother transitions, additional idle
  variety) is possible future work, not a defect.

## 5. Technical debt

- `apps/desktop`'s only automated frontend tests are `vitest` unit/
  component tests; there is no end-to-end test harness (e.g. Playwright
  wired into CI) — this phase's own in-browser verification was manual
  and one-off, not a repeatable suite.
- `useAvatarSocket`'s reconnect backoff is a fixed 2s delay, not
  exponential — acceptable for a single local, low-latency connection,
  but worth revisiting if the desktop shell ever needs to tolerate a
  flakier Local API connection.
