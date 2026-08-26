# Conversation

## 1. The one rule (brief §27)

"VOICE → TRANSCRIPT → PHASE 4 INTENT INTERPRETER... Voice layer handles
speech. Phase 4 handles intent." `VoiceConversationManager.submit_utterance`
(`app/services/voice/manager.py`) never calls `IntentInterpreter` itself —
it normalizes, detects language, resolves follow-ups, then creates an
ordinary `Task` row and calls the *exact* `AgentOrchestrator.run` a typed
`POST /tasks/{id}/run` call already uses. Same `IntentInterpreter`, same
`TaskPlanner`, same Policy Engine, same audit trail.

## 2. What the manager actually receives and does

`submit_utterance(db, session_id, raw_text, *, stt_confidence)` takes
already-transcribed text — no STT dependency itself. Per turn:

1. Barge-in check if `VoiceState.RESPONDING` (`BARGE-IN.md`).
2. `TRANSCRIBING → UNDERSTANDING` (language detection + normalization).
3. If a task is paused at `WAITING_PERMISSION`, the utterance is parsed as
   a confirmation reply instead of a new command (`VOICE-SECURITY.md`).
4. Otherwise: `resolve_followup` rewrites an ordinal/pronoun reference
   against `VoiceSession.last_candidates`/`last_task_goal`, then a new
   `Task` is created with the resolved text as `description` and run.
5. `ResponseGenerator` turns the resulting `TaskState` into speech.

## 3. Follow-up / pronoun resolution (brief §28-31)

`resolve_followup` (`voice/core/followup.py`) is pure text rewriting, never
a second interpretation path: `"open the second one"` with
`last_candidates = [project1.txt, project2.txt]` becomes `"open the
project2.txt"`, which is *still* parsed by the real `IntentInterpreter`
afterward. `last_candidates` is populated from the real
`AmbiguityCandidate` list `TaskPlanner` already builds
(`app/services/agent/planner.py`'s `PlanOutcome.candidates`) — persisted
onto `Task.result["candidates"]` by the orchestrator specifically so this
works (a Phase 5 addition, see `app/services/agent/orchestrator.py`'s
`AMBIGUOUS` branch). No candidate list is ever fabricated by the voice
layer itself.

Short-term only: `VoiceSession.last_candidates`/`last_task_goal` live in
memory for the current session and are never written to any long-term
memory store — brief explicitly scopes this to short-term context, not
Phase 6's permanent memory.

## 4. Corrections

`"Actually, I meant Spotify"` is not special-cased — it's just another
utterance. If a task is still paused waiting for input, the correction is
resolved the same way any follow-up is; if the prior task already
completed, it becomes an ordinary new command. No dedicated "correction"
grammar exists — the brief's acceptance test §129 (live correction
stopping speech) is satisfied by barge-in (`BARGE-IN.md`) plus ordinary
re-submission, not a third mechanism.

## 5. Verified

`tests/integration/test_voice_conversation.py` (8 tests) and
`tests/integration/test_voice_api.py` (3 tests) drive this manager against
the real `AgentOrchestrator`/Policy Engine/filesystem sandbox — completion,
failure, capability-unavailable, ambiguity + follow-up, confirmation
pause/resume/deny, barge-in, and transcript logging are all exercised for
real, not modeled.
