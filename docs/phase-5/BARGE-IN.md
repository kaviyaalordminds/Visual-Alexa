# Barge-In / Interruption

## 1. The state machine half

`VoiceState.RESPONDING → INTERRUPTED → LISTENING` (`VOICE-STATE-MACHINE.md`).
`VoiceConversationManager.submit_utterance` checks `session.status ==
RESPONDING` first, before anything else — if VEYRA is "speaking" when a
new utterance arrives, that is always a barge-in, whether or not the
words match a named interruption phrase (brief §13: *any* speech while
responding stops the current response).

## 2. Classification

`classify_interruption(text) -> InterruptionResult`
(`voice/core/interruption.py`) resolves matched phrases to one of four
`InterruptionType`s:

| Phrase | Type |
|---|---|
| `Stop.` / `Stop talking` / `Shut up` / `That's enough` | `STOP_SPEAKING` |
| `Cancel` / `Cancel that` / `Never mind` | `CANCEL_TASK` |
| `Wait` / `Hold on` / `Pause` | `PAUSE_TASK` |
| `Goodbye` / `Exit` / `End session` | `END_SESSION` |

Contextual disambiguation (brief §14's own example): a bare `"stop"`
(optionally followed only by speech-referring words like "talking") means
`STOP_SPEAKING`; `"stop"` followed by a named target (`"Stop Chrome"`,
`"Stop the download"`) means `CANCEL_TASK` instead.

## 3. What each type actually does

- `STOP_SPEAKING` — stops speech, returns to `LISTENING`. The task, if
  any, keeps running untouched.
- `CANCEL_TASK` — calls the real `request_cancellation(task_id)`
  (Phase 4's own cooperative cancellation signal, `app/services/agent
  /orchestrator.py`), clears `active_task_id`/`last_candidates`.
- `PAUSE_TASK` — **known limitation**: Phase 4's `AgentOrchestrator` has no
  real pause/resume mechanism (only cancellation and
  confirmation-resume), so `PAUSE_TASK` only ever pauses VEYRA's *speech*,
  never the underlying task execution. Documented directly in
  `app/services/voice/manager.py`'s `_handle_interruption`, not
  represented as a stronger guarantee than it delivers.
- `END_SESSION` — cancels any active task, transitions to `ENDED`, removes
  the session from the manager's registry.

Every matched interruption returns `stop_speaking=True` in the
`VoiceTurnResult` — a real caller's `AudioOutput.stop()` is meant to be
called unconditionally whenever this is set.

## 4. Verified

`tests/unit/test_voice_interruption.py` (11 cases, every named phrase plus
the "Stop Chrome" disambiguation and the empty/no-match cases);
`tests/integration/test_voice_conversation.py::test_barge_in_stop_speaking`
and `::test_end_session_interruption_ends_session`; security test
`test_9_cancelling_a_paused_task_via_voice_prevents_a_later_yes_from_resuming_it`
and `test_10_every_interruption_type_stops_speech_immediately`
(`tests/security/test_phase5_voice_security.py`) confirm cancellation is
real, not merely modeled.
