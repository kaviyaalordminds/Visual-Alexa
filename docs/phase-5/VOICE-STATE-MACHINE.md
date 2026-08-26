# Voice State Machine

## 1. Reused pattern, new table

Mirrors `veyra_contracts.tasks.is_legal_transition`/`TaskStateMachine`'s
exact discipline (`docs/phase-4/TASK-STATE-MACHINE.md`): a real,
unit-tested `_LEGAL_TRANSITIONS` table plus a pure `is_legal_transition`
function plus a thin `VoiceStateMachine` wrapper that is the *only* place
`VoiceSession.status` may be mutated, raising `IllegalVoiceTransitionError`
otherwise (`voice/core/state_machine.py`).

## 2. Brief §12/§43 consolidation

The brief describes both a "session status" list (§12) and a "state
machine" (§43) using the same value set. `VoiceState` (`voice/core/enums.py`)
unifies these into one enum and one field, `VoiceSession.status` — a
deliberate consolidation, not a missed requirement, the same approach
Phase 4 took mapping the brief's `CREATED`/`AWAITING_CONFIRMATION` onto
existing names.

## 3. Legal transitions

```
IDLE          -> WAKE_DETECTED, LISTENING
WAKE_DETECTED -> LISTENING, IDLE
LISTENING     -> TRANSCRIBING, IDLE
TRANSCRIBING  -> UNDERSTANDING, IDLE
UNDERSTANDING -> EXECUTING, RESPONDING   (RESPONDING direct: a clarifying
                                           question needs no EXECUTING step)
EXECUTING     -> RESPONDING
RESPONDING    -> IDLE, INTERRUPTED
INTERRUPTED   -> LISTENING, IDLE
RECOVERY      -> IDLE, ERROR
ERROR         -> RECOVERY                (only legal exit)
ENDED         -> (terminal)
```

`ERROR` and `ENDED` are additionally reachable from *any* non-terminal
state (the same "CANCELLED reachable from anywhere" rule Phase 1/4's
`TaskState` uses) — except leaving `ERROR` itself, whose only legal exit
is `RECOVERY`.

## 4. A real bug this table caught

The first version of `_LEGAL_TRANSITIONS` marked `ERROR`'s row as an empty
frozenset with a `# Terminal.` comment — but `ERROR`'s only intended exit,
`RECOVERY`, was never actually in that row, so
`is_legal_transition(ERROR, RECOVERY)` returned `False`, silently
contradicting the function's own top-of-body guard that assumes
`RECOVERY` is `ERROR`'s legal exit. Caught by
`tests/unit/test_voice_state_machine.py::test_errors_only_legal_exit_is_recovery`
during this phase's own verification, before anything shipped — fixed by
adding `VoiceState.ERROR: frozenset({VoiceState.RECOVERY})`. Direct
parallel to `docs/phase-4/TASK-STATE-MACHINE.md` §3's own three
real-bugs-caught list.

## 5. Verified

`tests/unit/test_voice_state_machine.py` (9 cases: happy path,
understanding-skips-executing, barge-in return-to-listening, illegal
transition raises without mutating state, error-reachable-from-anywhere,
error's-only-exit, ended-is-terminal, can_transition-is-non-mutating).
