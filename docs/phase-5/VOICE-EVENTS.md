# Voice Events

## 1. Reused infrastructure

`event_bus`/`EventType` (Phase 1, extended in Phase 4) already supports
exactly the publish/subscribe shape `voice.*` events need — extended
additively, following the same pattern Phase 4 used for `task.*`
(`veyra_contracts.enums.EventType`):

```
voice.wake_detected
voice.listening_started / voice.listening_stopped
voice.transcript.partial / voice.transcript.final
voice.language.detected
voice.intent.received
voice.response.started / voice.response.finished
voice.interrupted
voice.error
voice.ui_state.changed
```

No new persisted `voice_events` table — a second copy of what
`event_bus`/`AuditLog` already provide would duplicate their job, the same
reasoning Phase 4 applied to rejecting a `task_events` table
(`docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md` §8).

## 2. What's actually wired to publish them today

The enum values exist and are real (`veyra_contracts.enums.EventType`),
but `VoiceConversationManager` does not yet call `event_bus.publish_type`
for any of them — it relies on the underlying `task.*` events Phase 4
already publishes during `AgentOrchestrator.run`
(`app/api/events.py`'s existing WebSocket fan-out already carries those).
Wiring the voice-specific events is straightforward additive work
(the exact call pattern `orchestrator.py` already uses throughout) left
for whichever phase first has a real caller (a live desktop UI) that needs
them — declaring and never firing them would be no better than not having
them, so this gap is recorded here rather than hidden.

## 3. UI-state events for a future avatar (brief §69)

`voice.ui_state.changed` is reserved for a `VoiceUIState`-shaped payload
(`IDLE`/`LISTENING`/`THINKING`/`EXECUTING`/`WAITING_CONFIRMATION`/
`SPEAKING`/`SUCCESS`/`ERROR`) that a future avatar would consume to drive
expressions — no such payload shape or avatar exists yet (brief §132
explicitly forbids building the avatar this phase). The event name exists
so that work has a landing point without touching this phase's contracts
again.

## 4. Verified

The enum values themselves are exercised by `veyra_contracts`'s existing
test suite (string-enum membership); no dedicated publish-path test exists
yet since nothing calls `publish_type` for them (§2) — recorded as a known
gap in `PHASE-5-TEST-RESULTS.md`.
