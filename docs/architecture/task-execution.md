# Task Execution

The authoritative state machine is `14-TASK-LIFECYCLE.md` — this
document describes how a `Task` actually moves through it end to end via
the real HTTP API, and what Phase 13 changed about what gets persisted
along the way. See `runtime.md` (this directory) for which component
owns each stage.

## The real pipeline

```
POST /tasks                    -> Task{state=RECEIVED}
POST /tasks/{id}/run           -> AgentOrchestrator.run() (background task)
  IntentInterpreter.interpret()   -> StructuredIntent   (UNDERSTANDING)
  TaskPlanner.create_plan()       -> ExecutionPlan       (PLANNING)
  for each PlanStep:
    PolicyEngine check              (WAITING_PERMISSION if denied+confirmable)
    execute_tool_call()              (EXECUTING)
    step-level observation recorded  (OBSERVING)
    ActionResult.verification        (VERIFYING)
    on failure: RecoveryManager.decide() -> RETRY|REPLAN|ASK_USER|ABORT (RECOVERING)
  -> COMPLETED | FAILED | CANCELLED | TIMED_OUT
```

`GET /tasks/{id}` and `GET /tasks/{id}/steps` are the real, live progress
views — the same shape `apps/desktop/src/tasks/TaskPanel.tsx` polls
(`docs/phase-13-audit.md §8`; previously nothing in the desktop app
called this API at all). `POST /tasks/{id}/confirm` resumes the *same*
remaining plan after a `WAITING_PERMISSION` pause — never a replan
(`docs/phase-4/CONFIRMATION.md`).

## What actually gets persisted on a `Task` row

Most of Task's real fields map directly onto columns: `description`,
`state`, `current_step`/`total_steps`, `failure_reason`, `result`. Two
things worth calling out precisely, because they're easy to assume are
richer than they are:

- **`plan` is not a durable, queryable field.** It lives transiently in
  `task.result` while `WAITING_PERMISSION`/`PAUSED`, and is cleared once
  resumed. A completed task's plan is not retrievable from the `Task`
  row afterward — but every step's `tool_id`/`arguments` remain on its
  `TaskStep` row via `GET /tasks/{id}/steps`, which is the real record
  of what was planned and run.
- **`recovery_attempts` (Phase 13 addition).** `TaskContext.retry_count`/
  `replan_count` are tracked in memory for the duration of a run and are
  now persisted onto `Task.extra_metadata` (`{"retry_count": ...,
  "replan_count": ...}`) at every terminal transition — `_fail`,
  `_timeout`, `_fail_at_planning`, and the success path in
  `_execute_plan` all call `_record_recovery_attempts` before saving.
  Before this, the information was computed correctly but silently lost
  the moment a task reached a terminal state
  (`docs/phase-13-audit.md §2`). `extra_metadata` is not exposed on the
  `TaskOut` API response — read it via a direct `TaskRow` query (see
  `tests/integration/test_agent_tasks_api.py::
  test_recovery_attempts_are_persisted_on_the_task_row`).

## Idempotent retries

A step retried by `RecoveryManager.RETRY` reuses the exact `call_id` of
its original attempt (`AgentOrchestrator._step_call_id`). If that
attempt actually succeeded server-side despite the caller seeing a
timeout, the retry returns the cached success instead of re-executing —
see `runtime.md` and `docs/phase-13-audit.md §4` for the full design
rationale (why only successes are cached, never failures).

## Cooperative cancellation and pause

`POST /tasks/{id}/cancel` and `/pause` set a signal
`AgentOrchestrator` checks between steps — never a hard kill mid-tool-
call. `/cancel` is checked on any active state; `/resume` after a pause
continues the *same* plan (not a replan), matching `docs/phase-5/
BARGE-IN.md`.
