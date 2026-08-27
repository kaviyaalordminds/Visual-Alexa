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
- `PAUSE_TASK` — pauses VEYRA's *speech* only; see §5 for why real task
  pausing exists but isn't wired to this particular interruption.
- `END_SESSION` — cancels any active task, transitions to `ENDED`, removes
  the session from the manager's registry.

Every matched interruption returns `stop_speaking=True` in the
`VoiceTurnResult` — a real caller's `AudioOutput.stop()` is meant to be
called unconditionally whenever this is set.

## 5. Real task pausing exists — at the orchestrator/HTTP level

`TaskState.PAUSED` is a real, additive Phase 5 state
(`veyra_contracts.enums.TaskState`, `veyra_contracts.tasks
._LEGAL_TRANSITIONS`: `EXECUTING → PAUSED → EXECUTING`, `CANCELLED`
reachable from `PAUSED` like any other non-terminal state).
`request_pause(task_id)`/`AgentOrchestrator.resume_after_pause`
(`app/services/agent/orchestrator.py`) mirror `request_cancellation`/
`resume_after_confirmation` exactly: a cooperative in-memory signal
checked once per step (`_check_paused`, right alongside `_check_cancelled`
in `_execute_plan`'s loop), persisting the *remaining* plan into
`task.result["paused_plan"]` so resuming continues the same plan, never a
replan. `POST /tasks/{id}/pause` and `POST /tasks/{id}/resume`
(`app/api/tasks.py`) expose this over HTTP, for a task whose execution
genuinely runs concurrently with other requests (i.e. started via
`POST /tasks/{id}/run`'s background execution).

**Why the voice layer's own `PAUSE_TASK` doesn't call `request_pause`:**
`VoiceConversationManager.submit_utterance` `await`s
`AgentOrchestrator.run` to completion before returning — a voice turn's
execution is synchronous with respect to that turn, so by the time a
barge-in interruption can even be recognized (the *next* `submit_utterance`
call), the run it would apply to has already reached a terminal or
waiting state. Calling `request_pause` anyway would leave a dangling flag
that could wrongly re-pause a *later*, unrelated resume of the same task
(e.g. after a `WAITING_PERMISSION` confirmation) — worse than not pausing
at all. This is a real architectural limit of the current per-turn
design, not an oversight; it would need voice turns to run task execution
concurrently with the ability to receive a new utterance to close, which
is out of Phase 5's scope.

**What voice *does* do with a real pause:** `VoiceConversationManager
._handle_resume` recognizes when `session.active_task_id` refers to a
task genuinely in `PAUSED` state (e.g. paused via the HTTP endpoint by
another caller, or by a future concurrent voice architecture) and
resumes it for real on "continue"/"resume" (added to
`voice.core.confirmation`'s `AFFIRM` phrases), or cancels it on a denial
— the same `AFFIRM`/`DENY`/`UNCLEAR` discipline `_handle_confirmation`
uses, gated by the same STT-confidence floor. Resuming a pause is never a
security gate itself (brief §14); any step in the resumed plan that
genuinely needs confirmation still goes through the real Policy Engine
independently.

## 6. Verified

`tests/unit/test_voice_interruption.py` (11 cases, every named phrase plus
the "Stop Chrome" disambiguation and the empty/no-match cases);
`tests/integration/test_voice_conversation.py::test_barge_in_stop_speaking`,
`::test_end_session_interruption_ends_session`, and
`::test_voice_resumes_a_paused_task_on_continue` (a task paused externally,
resumed for real by a voice "continue"); `tests/integration
/test_agent_tasks_api.py::test_pause_before_run_then_resume_executes_the_full_plan`
(pause before any step runs, resume, the *same* plan completes for real —
proving nothing executes while paused and the Policy Engine's own
independent confirmation gate for `filesystem.create_folder` still isn't
bypassed by pausing), `::test_resume_without_a_pause_is_rejected`,
`::test_pause_on_a_terminal_task_is_a_harmless_noop`;
`tests/unit/test_task_transitions.py::test_executing_can_pause_and_resume`
and `::test_paused_only_resumes_or_cancels_never_skips_to_terminal`;
security tests
`test_9_cancelling_a_paused_task_via_voice_prevents_a_later_yes_from_resuming_it`
and `test_10_every_interruption_type_stops_speech_immediately`
(`tests/security/test_phase5_voice_security.py`) confirm cancellation is
real, not merely modeled.
