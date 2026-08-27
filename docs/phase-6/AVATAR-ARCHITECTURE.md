# Avatar Architecture

## 1. Shape

```
AgentOrchestrator / VoiceConversationManager (real transitions)
        │
        ▼
compute_agent_state_from_task() / direct AgentState literals
        │
        ▼
event_bus.publish_type(VOICE_UI_STATE_CHANGED, session.id, payload)
        │
        ▼
/events WebSocket (Phase 1, unchanged)
        │
        ▼
apps/desktop: useAvatarSocket -> applyAvatarEvent (pure reducer)
        │
        ▼
Avatar.tsx (SVG, driven by AgentState + viseme timeline)
```

No new transport, no new state-computation authority on the client: the
desktop shell never decides what state VEYRA is in, it only renders what
the Local API already decided (CLAUDE.md: the desktop shell talks only to
the Local API). The reducer (`apps/desktop/src/avatar/state.ts`) is pure
specifically so it never needs the socket to be tested — see
`PHASE-6-TEST-RESULTS.md`.

## 2. `AgentState` (`veyra_contracts.enums.AgentState`)

`IDLE, LISTENING, UNDERSTANDING, THINKING, PLANNING, EXECUTING, WAITING,
CONFIRMING, RECOVERING, SPEAKING, SUCCESS, ERROR, PAUSED`.

`compute_agent_state_from_task` (`veyra_contracts/avatar.py`) maps every
`TaskState` onto one of these:

| TaskState | AgentState |
|---|---|
| RECEIVED | THINKING |
| UNDERSTANDING | UNDERSTANDING |
| PLANNING | PLANNING |
| WAITING_PERMISSION | CONFIRMING |
| EXECUTING / OBSERVING / VERIFYING | EXECUTING |
| RECOVERING | RECOVERING |
| WAITING_USER | WAITING |
| PAUSED | PAUSED |
| COMPLETED | SUCCESS |
| FAILED / TIMED_OUT | ERROR |
| CANCELLED | IDLE |

`SPEAKING` has no `TaskState` row — VEYRA can be speaking a response
about a task that is already terminal, so it's set directly by
`VoiceConversationManager`, never derived.

## 3. Real trigger points (`VoiceConversationManager`)

This is the one caller that exists today, so these are the only points
`voice.ui_state.changed` can genuinely fire from — the same discipline
`_publish`'s docstring already applied to the other `voice.*` events:

| Point | AgentState | Why here |
|---|---|---|
| `start_session` | LISTENING | Mirrors the real `VOICE_LISTENING_STARTED` transition — no wake-word detector in this phase either, so a session starts listening immediately. |
| `submit_utterance`, right after `VOICE_LISTENING_STOPPED` | THINKING | Everything between "stopped listening" and "have a result" — transcribing, language detection, understanding, planning, execution, recovery — is opaque from this synchronous voice turn's own vantage point (the same architectural fact `BARGE-IN.md` §5 documents for `PAUSE_TASK`). One honest bucket, not a fabricated granular sequence. |
| `_log_turn`, whenever `response_text` is non-empty | SPEAKING (+ visemes, + optional `outcome`) | The one place every turn passes through regardless of which branch handled it (mishear check, confirmation, resume, or a brand-new task) — already where `VOICE_RESPONSE_STARTED` fires, from the same real text. |
| `finish_response` | IDLE | Real playback (or a text-only caller) finished — mirrors `VOICE_RESPONSE_FINISHED`. |
| `_handle_interruption`, STOP_SPEAKING / PAUSE_TASK | LISTENING | These are the only two interruption outcomes with `should_speak=False` — `_log_turn`'s SPEAKING publish never fires for them, so this is the only place the avatar learns VEYRA stopped talking. |

`outcome` (an optional second `AgentState` riding on a `SPEAKING` event)
is the real terminal/waiting `AgentState` the underlying task reached,
computed via `compute_agent_state_from_task(task.state)` at the three
call sites that have a concrete task: the main new-task path, the
confirmation-resume path, and the pause-resume path. It lets the
renderer show (for example) a concerned expression while speaking an
error message, without inventing a second, competing event.

## 4. Payload shape

```json
{
  "agent_state": "SPEAKING",
  "visemes": [{"shape": "AI", "start_ms": 0, "duration_ms": 90}, ...],
  "outcome": "SUCCESS"
}
```

`visemes`/`outcome` are only ever present alongside `agent_state:
"SPEAKING"` with non-empty real text — never fabricated for a silent
turn. See `packages/contracts/typescript/src/events.ts`'s
`AvatarUIStatePayload` for the mirrored type.

## 5. The visual identity itself

`apps/desktop/src/avatar/`:

- `state.ts` — the pure `applyAvatarEvent` reducer plus `activeVisemeAt`
  and `expressionStateFor` (outcome-aware expression selection).
- `visuals.ts` — pure `AgentState -> {auraColor, pulseSpeedMs, eyeState,
  browTiltDeg, label}` and `VisemeShape -> {rx, ry}` mouth-ellipse data.
  No animation logic, only data — the same "pure mapping, separately
  tested" shape as the backend's `compute_agent_state_from_task`.
- `useAvatarSocket.ts` — the only place that touches the real `/events`
  WebSocket; reconnects on close (the Local API may not be running yet).
- `Avatar.tsx` — an original, abstract SVG presence (not photorealistic,
  not any existing product's mark, per `docs/research/
  07-VEYRA-DIFFERENTIATORS.md` §11's "an original avatar with an explicit
  state machine tied to task execution state"): a stylized face with a
  flowing asymmetric hair silhouette, eyes/eyebrows driven by
  `eyeState`/`browTiltDeg`, a soft pulsing color aura driven by
  `auraColor`/`pulseSpeedMs`, and a mouth that cycles through the real
  viseme timeline while `agentState === "SPEAKING"` (via
  `requestAnimationFrame`, reading `activeVisemeAt(visemes, elapsed)`),
  or a small state-appropriate curve otherwise (a smile for SUCCESS, a
  frown for ERROR, a neutral line everywhere else).

## 6. What this phase did not attempt

- **Audio-driven or facial-capture-driven lip sync** — see `LIP-SYNC.md`.
- **Granular in-task-step avatar reactions during a voice-triggered task
  run** — `task.*` events (`TASK_STEP_STARTED` etc.) already publish in
  real time via the same `event_bus`, but a voice turn's own execution is
  synchronous end-to-end (`submit_utterance` awaits `AgentOrchestrator.run`
  to completion), so correlating a task's granular steps back to the
  voice session that spawned it would need new plumbing (a `Task` ->
  `VoiceSession` link) for a use case — live step-by-step avatar reactions
  during a bundled "thinking" phase — that doesn't have an obvious payoff
  yet. Documented here as a deliberate scoping choice, the same way
  `BARGE-IN.md` §5 documents `PAUSE_TASK`'s own synchronous-turn
  limitation, not silently dropped.
- **Wake-word/streaming-STT-driven avatar states** — `voice.wake_detected`
  and `voice.transcript.partial` still have no real trigger (unchanged
  from Phase 5); the avatar has nothing to render from them yet either.
