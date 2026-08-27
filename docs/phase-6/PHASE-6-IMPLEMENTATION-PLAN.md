# Phase 6 Implementation Plan — Visual Female AI Identity / Avatar Engine

Written the same way Phases 2-5's own plans were: what the repository
already had before this phase touched it, what's genuinely reusable vs.
new, and the decisions made with rationale.

## 1. What Phase 1-5 actually implemented (repository inspection findings)

- **The avatar vocabulary already existed, unused.** `veyra_contracts.
  enums.AgentState` (Phase 4) was defined with a docstring promising "a
  future avatar/UI can map `TaskState` onto" — but grepping the codebase
  found exactly zero callers. `docs/phase-4/AGENT-ARCHITECTURE.md` §5
  says so explicitly: "No animation, no avatar rendering — the enum and
  the mapping convention are the only Phase 4 deliverable here."
- **`EventType.VOICE_UI_STATE_CHANGED` already existed, unpublished.**
  Declared in Phase 5, and `VoiceConversationManager._publish`'s own
  docstring said why: "declared in `EventType` but [has] no real trigger
  in this phase... no avatar." Phase 5's own test results (§5) listed
  this as a known limitation, not a bug — there was nothing to trigger it
  with yet.
- **The desktop shell has a real, working `/events` WebSocket already.**
  `services/local-api/app/api/events.py` (Phase 1) is a real, tested
  fan-out over the same `EventBus` every publisher already uses — no new
  transport was needed, only a real consumer.
- **The TypeScript contracts package had drifted from the Python one.**
  `packages/contracts/typescript/src/enums.ts`'s `TaskState`, `EventType`,
  and a Phase-1-era `AvatarState` type were all stale (missing `PAUSED`/
  `TIMED_OUT`, missing every Phase 4/5 `task.*`/`voice.*` event, and a
  values list that didn't match `AgentState` at all despite the file's own
  "keep in sync" comment) — nothing in the desktop app consumed any of
  them yet, so nothing broke, but they had to be corrected before the
  avatar could consume `/events` with real types.
- **No real TTS audio pipeline exists in this environment** (Phase 5,
  reconfirmed) — no audio hardware, no library. There is no real
  phoneme/amplitude timing anywhere in this codebase to drive a mouth
  animation from.

## 2. The central technical decision: what's genuinely real here

Same split Phase 5 drew for audio: everything that is pure logic —
computing which `AgentState` to show, and a deterministic viseme timeline
from real response text — is fully real, fully tested, and genuinely
wired to the actual voice pipeline. The one thing that cannot be real in
this environment is audio-driven lip sync, because there is no audio.
Rather than fake a waveform, `docs/phase-6/LIP-SYNC.md` documents exactly
what the substitute is and why, the same way Phase 5 was honest about
`Mock*`/`NotConfigured*` providers.

## 3. What was built

1. **`veyra_contracts.avatar.compute_agent_state_from_task`** — the real
   `TaskState` -> `AgentState` mapping function Phase 4 promised as a
   convention but never implemented. Exhaustive over every `TaskState`
   (a missing case is a `KeyError`, not a silent wrong answer).
2. **`AgentState.SPEAKING` and `AgentState.PAUSED`** added additively —
   `SPEAKING` has no `TaskState` equivalent (VEYRA can be speaking about
   an already-terminal task) so it's set directly by the voice layer;
   `PAUSED` mirrors `TaskState.PAUSED` (Phase 5) 1:1.
3. **`voice.core.visemes.text_to_visemes`** — a deterministic, stdlib-only
   mouth-shape timeline computed from the real response text. See
   `LIP-SYNC.md`.
4. **`VoiceConversationManager` now publishes `voice.ui_state.changed`
   for real** at every point the pipeline can genuinely observe a
   transition — see `AVATAR-ARCHITECTURE.md` §3.
5. **TypeScript contracts corrected and extended** — `TaskState`,
   `EventType` brought back in sync with Python; the stale `AvatarState`
   type renamed to `AgentState` and completed; new `events.ts` mirroring
   `veyra_contracts.events.Event` and the `voice.ui_state.changed` payload
   shape.
6. **The actual avatar** — `apps/desktop/src/avatar/` — an original,
   abstract visual identity rendered in SVG, driven entirely by the real
   `/events` WebSocket through a pure, unit-tested reducer
   (`applyAvatarEvent`). See `AVATAR-ARCHITECTURE.md`.

## 4. What was deliberately not built

Per CLAUDE.md's phase discipline, this phase stops at the avatar/visual-
identity engine:

- No real TTS audio, wake-word, or STT model (unchanged from Phase 5 —
  no audio hardware/library in this environment).
- No IoT, WhatsApp, full browser agent, long-term personal memory, or
  autonomous background behavior — explicitly out of scope per CLAUDE.md
  until their own phases.
- No facial-capture-driven or audio-driven lip sync — see `LIP-SYNC.md`
  for exactly what ships instead and why.

## 5. Testing

- Backend: `tests/unit/test_avatar_mapping.py` (exhaustive `TaskState` ->
  `AgentState` coverage), `tests/unit/test_voice_visemes.py` (11 tests on
  `text_to_visemes`), `tests/integration/test_avatar_ui_state.py` (5
  end-to-end tests against the real `VoiceConversationManager` and real
  `event_bus`), plus the existing `test_voice_events.py` updated now that
  `voice.ui_state.changed` genuinely fires.
- Frontend: `apps/desktop` gained a test runner (`vitest` + Testing
  Library — none existed before this phase) with 53 tests covering the
  event reducer (`state.test.ts`, exhaustive over every `AgentState`),
  the visual mapping (`visuals.test.ts`, exhaustive over every
  `AgentState`/`VisemeShape`), and a render smoke test (`Avatar.test.tsx`).
- Manually verified in a real browser (Chromium via Playwright) against
  the actual `vite` dev build, simulating real `voice.ui_state.changed`
  WebSocket frames — confirmed the aura color, eyes, eyebrows, and mouth
  shape all change correctly and distinctly across LISTENING, THINKING,
  SPEAKING (both SUCCESS- and ERROR-tinted), and CONFIRMING.
