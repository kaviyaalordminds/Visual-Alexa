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

`VoiceConversationManager` (`app/services/voice/manager.py`) publishes
seven of the nine events for real, via a `_publish` helper keyed by
`session.id` as the correlation id (there is no `Task.correlation_id` yet
at most of these call sites):

| Event | Fires when |
|---|---|
| `voice.listening_started` | `start_session` transitions to `LISTENING` |
| `voice.listening_stopped` | `submit_utterance`, just before `TRANSCRIBING` |
| `voice.transcript.final` | Every turn, in `_log_turn` — payload is the redacted utterance text |
| `voice.language.detected` | Every turn, right after `detect_language` — language/confidence/mixed_language |
| `voice.intent.received` | After `AgentOrchestrator.run` returns — payload is `task.normalized_goal`, the real classified intent |
| `voice.response.started` | Every turn a response has non-empty text, in `_log_turn` — payload is the redacted response text |
| `voice.response.finished` | `finish_response`, once real/simulated playback completes |
| `voice.interrupted` | Top of `_handle_interruption` — payload names the `InterruptionType` |

Three are deliberately **not** published — faking them would be worse than
not having them:

- `voice.wake_detected` — no real wake-word detector exists in this phase
  (`AUDIO-PIPELINE.md` §3-4).
- `voice.transcript.partial` — no real streaming STT provider exists; only
  a single final transcript per turn is ever available.
- `voice.ui_state.changed` — no avatar consumes it yet (brief §132
  explicitly forbids building one this phase); see §3.
- `voice.error` — no real audio-pipeline error condition (mic/wake-word/
  STT/TTS failure) can occur in a text-only pipeline with no hardware;
  publishing it against, say, an `UnknownVoiceSessionError` caller misuse
  would misrepresent a programming error as a voice-hardware fault.

## 3. UI-state events for a future avatar (brief §69)

`voice.ui_state.changed` is reserved for a `VoiceUIState`-shaped payload
(`IDLE`/`LISTENING`/`THINKING`/`EXECUTING`/`WAITING_CONFIRMATION`/
`SPEAKING`/`SUCCESS`/`ERROR`) that a future avatar would consume to drive
expressions — no such payload shape or avatar exists yet (brief §132
explicitly forbids building the avatar this phase). The event name exists
so that work has a landing point without touching this phase's contracts
again.

## 4. Verified

`tests/integration/test_voice_events.py` subscribes to the real
`event_bus` and drives a full voice turn, a barge-in, and a
secret-bearing utterance through the real `VoiceConversationManager`:
confirms all seven wired events actually publish in the right places,
confirms the three unwired events (`voice.wake_detected`,
`voice.transcript.partial`, `voice.ui_state.changed`) never fire, and
confirms the `voice.transcript.final` payload is redacted before
publishing — the same discipline `VOICE-PRIVACY.md` requires for the
persisted transcript.
