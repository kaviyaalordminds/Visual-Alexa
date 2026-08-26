# Error Model & Recovery

## New `ErrorCategory` values

Added additively to `veyra_contracts.enums.ErrorCategory` (nothing renamed
— every Phase 1 code is unchanged): `APPLICATION_LAUNCH_FAILED`,
`WINDOW_NOT_FOUND`, `WINDOW_NOT_ACTIVE`, `UI_ELEMENT_DISABLED`,
`PATH_NOT_ALLOWED`, `PATH_PROTECTED`, `TARGET_CONTEXT_REQUIRED`,
`INPUT_BLOCKED`, `VERIFICATION_FAILED`, `TOOL_DISABLED`,
`OPERATION_CANCELLED`, `UNKNOWN_WINDOWS_ERROR`. One addition beyond the
brief's own list: `PLATFORM_NOT_SUPPORTED`, needed for the honest
non-Windows failure path (see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2 and §6).

`UI_ELEMENT_NOT_FOUND` from the brief's list is **not** a new code — it
maps onto Phase 1's existing `UI_NOT_FOUND`, which already means exactly
this. Adding a near-duplicate would have split error-handling logic for
no semantic gain.

## Retryable categories

`veyra_contracts.errors.RETRYABLE_CATEGORIES` gains `WINDOW_NOT_FOUND`,
`UI_NOT_FOUND`, and `UNKNOWN_WINDOWS_ERROR` — all three are exactly the
"the target hasn't appeared yet" class of transient failure the brief's
§26 retry policy describes, and are already bounded by
`TaskBudget.max_recovery_attempts` (Phase 1's task lifecycle) rather than
being unboundedly retried. Every other new code (`PATH_NOT_ALLOWED`,
`PATH_PROTECTED`, `TARGET_CONTEXT_REQUIRED`, `PERMISSION_DENIED`,
`INPUT_BLOCKED`, `TOOL_DISABLED`, `PLATFORM_NOT_SUPPORTED`,
`APPLICATION_LAUNCH_FAILED`, `VERIFICATION_FAILED`, `OPERATION_CANCELLED`)
is explicitly **not** retryable — per docs/phase-2 §26, "do not retry
destructive operations automatically," and more generally: none of these
are transient conditions a bare retry would resolve.

## Where errors are constructed

`ErrorInfo.build(code, message, correlation_id, ...)` — the same Phase 1
factory, unchanged — is used throughout
`app/services/computer_control/support.py`'s `callable_executor`, so
`retryable` is always derived consistently from the shared
`RETRYABLE_CATEGORIES` set rather than being hand-set per call site.

## `ToolLogicError`: one exception class, one mapping point

Every Phase 2 tool-logic function raises `app.services.computer_control.support.ToolLogicError(code, message)`
on a known failure rather than hand-constructing an `ActionResult(status=FAILED, ...)`
at every call site. `callable_executor` catches it exactly once and builds
the `ErrorInfo`/`ActionResult`/`ToolResult` triad consistently. A second,
narrower catch handles `pydantic.ValidationError` specifically (mapped to
`TARGET_CONTEXT_REQUIRED`) — see `docs/phase-2/INPUT-CONTROL.md`.

## What Phase 2 does *not* attempt

A live `RECOVERING`-state replanning loop (docs/architecture/14-TASK-LIFECYCLE.md's
`RECOVERING` task state) requires a live planner to decide retry vs.
replan vs. ask-the-user, which does not exist yet (explicitly out of
scope — brief §46). Phase 2 delivers the error taxonomy and
retryable/non-retryable classification that a future planner will consume,
not the planner itself.
