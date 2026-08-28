# Recovery (Phase 11)

`RecoveryManager` (`app/services/agent/recovery.py`) is unchanged by
Phase 11 — its strategy-selection table, budget bounding, and
category-classification are exactly as documented in
`docs/phase-4/RECOVERY.md`, which remains the source of truth for *how a
strategy is chosen*. This page documents the one thing that changed:
*what happens once `REPLAN` is chosen.*

## Before Phase 11

`AgentOrchestrator._recover`'s `REPLAN` branch was an always-fails stub:
it transitioned the task to `PLANNING` and then unconditionally reported
"Replanning is not yet supported for this goal." The *first* version of
that stub had a real bug (documented in `docs/phase-4/PHASE-4-TEST-
RESULTS.md`): it tried `PLANNING -> FAILED` via `_fail()`, which is not a
legal transition, and would have raised `IllegalTaskTransitionError`
every time `REPLAN` was genuinely reached. That bug was fixed by
short-circuiting straight from `RECOVERING -> FAILED` — a legal
transition — but the strategy itself remained "always fail," just
crash-free.

## After Phase 11 — real re-planning

```python
# app/services/agent/orchestrator.py, AgentOrchestrator._recover()
if decision.strategy == RecoveryStrategy.REPLAN:
    context.replan_count += 1
    tracker.record_replan()
    budget_reason = tracker.budget_exceeded_reason()
    if budget_reason:
        await self._timeout(session, sm, task, budget_reason)
        return False

    intent = (
        StructuredIntent.model_validate(task.normalized_goal)
        if task.normalized_goal else None
    )
    if intent is None or intent.status != "UNDERSTOOD":
        await self._fail(session, sm, task, "Replanning failed: ...",
                          code=ErrorCategory.INVALID_PLAN)
        return False

    sm.transition(TaskState.PLANNING)          # legal: RECOVERING -> PLANNING
    await self._save(session, task)
    await event_bus.publish_type(EventType.TASK_RECOVERY_COMPLETED, ...)
    await event_bus.publish_type(EventType.TASK_PLANNED, ...)
    await self._plan_from_intent(session, sm, task, intent, tracker, context)
    return False
```

`_plan_from_intent` is the exact function `run()` uses for the task's
first plan — factored out specifically so a replan's `AMBIGUOUS`/
`CAPABILITY_UNAVAILABLE`/`UNSAFE`/`INVALID`/`PLANNED` handling is
byte-for-byte the same code as the original plan's, not a second,
subtly-different branch that could drift. The intent re-planned against
is `task.normalized_goal` — the `StructuredIntent` captured once at task
creation (`IntentInterpreter` is not re-run; the user's original request
doesn't change mid-task) — but the planner's own inputs
(`search`/`memory_lookup`) are freshly re-invoked, so the *plan* reflects
current state even though the *intent* doesn't.

## Why this is safe

- **Same execution path.** A `PLANNED` outcome from a replan hands off to
  the same `_execute_plan` every plan runs through — no orchestrator-side
  shortcut around Policy Engine/Tool Registry/audit logging.
- **Doubly bounded.** `RecoveryManager.decide()` won't choose `REPLAN`
  once `replan_count >= budget.max_replans`; `LoopBudgetTracker`
  independently re-checks `total_replans > budget.max_replans` before
  every attempt. Once exhausted, the next failure escalates to
  `ASK_USER` — never a silent failure, never an infinite loop.
- **A legal transition, not a new one.** `RECOVERING -> PLANNING` was
  already in `veyra_contracts.tasks._LEGAL_TRANSITIONS` (added when
  Phase 4's diagram first anticipated `REPLAN`); Phase 11 needed zero
  contract changes.

## Verified

- `tests/integration/test_agent_tasks_api.py::
  test_replan_recovers_when_the_replanned_attempt_succeeds` — a tool call
  that fails once then succeeds: the task reaches `COMPLETED` through the
  freshly-built plan, proving real recovery, not merely "doesn't crash."
- `tests/integration/test_agent_tasks_api.py::
  test_replan_exhausted_asks_user_never_crashes` — every tool call always
  fails; with `max_replans=1` one real replan attempt happens, fails too,
  and the task correctly lands at `WAITING_USER` (not `FAILED`, not a
  crash) with a clarifying question naming the problem.
- `tests/unit/test_agent_recovery.py` — unchanged, still exercises every
  `RecoveryManager.decide()` category/budget combination in isolation.

## What's still deliberately out of scope

Replanning re-runs the *same deterministic templates* — it is not a
different plan shape, a different goal, or an LLM-generated alternative
strategy. If the environment genuinely hasn't changed, a replan produces
an identical plan to the one that just failed (expected, not a bug — the
templates are pure functions of their inputs). A future, smarter planner
that reasons about *why* the previous attempt failed and adapts its
strategy accordingly remains out of scope, matching this phase's "do not
create a second AI architecture" / "do not overbuild" constraints.
