# Recovery

`RecoveryManager` (`app/services/agent/recovery.py`) — diagnostic, not
blind retry (`docs/architecture/14-TASK-LIFECYCLE.md` §3, carried into
Phase 4).

## 1. Strategy selection

A pure function of the failed step's `ErrorCategory` and how many
attempts have already been spent:

| Category | Strategy |
|---|---|
| `UI_NOT_FOUND`, `AMBIGUOUS_TARGET` | `REGROUND` (re-observe/re-ground), then `ASK_USER` once attempts are exhausted |
| `VERIFICATION_FAILED`, `STATE_MISMATCH` | `REOBSERVE`, then `REPLAN`, then `ASK_USER` |
| Anything in `veyra_contracts.errors.RETRYABLE_CATEGORIES` (Phase 1's own set — `TIMEOUT`, `NETWORK_ERROR`, `TOOL_FAILURE`, `WINDOW_NOT_FOUND`, ...) | `RETRY`, then `REPLAN`, then `ASK_USER` |
| `APPLICATION_NOT_FOUND`, `APPLICATION_LAUNCH_FAILED`, `FILE_NOT_FOUND`, `PLATFORM_NOT_SUPPORTED`, `TOOL_DISABLED`, `UNKNOWN_TOOL`, `CAPABILITY_UNAVAILABLE`, `PATH_NOT_ALLOWED`, `PATH_PROTECTED`, `VALIDATION_ERROR`, `INVALID_PLAN` | `ABORT` immediately — permanent, never retried |
| Anything else | `ABORT` |

Reusing `RETRYABLE_CATEGORIES` (Phase 1) rather than a second taxonomy
keeps "is this retryable" a single source of truth — see
`PHASE-4-IMPLEMENTATION-PLAN.md` §1 for why a parallel `FailureCategory`
enum was rejected in favor of extending `ErrorCategory`.

## 2. Every strategy is budget-bounded

`retry_count`/`replan_count` are threaded through every decision;
`RecoveryManager` never recommends `RETRY`/`REOBSERVE`/`REGROUND` once
`retry_count >= budget.max_recovery_attempts`, and never `REPLAN` once
`replan_count >= budget.max_replans` — both escalate to `ASK_USER`
instead. `LoopBudgetTracker` (see `TASK-ENGINE.md`) is a second,
independent hard stop across the *whole* run.

## 3. `REPLAN` — implemented as a documented gap, not silently skipped

`AgentOrchestrator._recover`'s `REPLAN` branch transitions the task to
`PLANNING` and then honestly reports "Replanning is not yet supported for
this goal" rather than either crashing or fabricating a fake replan. The
deterministic templates in Phase 4 rarely need a real replan (an
`open_file`/`search_files` failure is almost always permanent —
`FILE_NOT_FOUND`, `PATH_NOT_ALLOWED` — which routes to `ABORT`, not
`REPLAN`, before this gap is ever reached in practice). See
`PHASE-4-TEST-RESULTS.md` known limitations.

## 4. Verified

`tests/unit/test_agent_recovery.py` (9 tests) — every category/budget
combination above, pure Python, no OS dependency, plus
`tests/security/test_agent_adversarial.py::test_infinite_retry_is_bounded_by_budget_never_hangs`
proving a permanently-failing step reaches a terminal state within the
configured budget rather than hanging.
