# Task Lifecycle (Phase 11)

The state machine itself is unchanged by Phase 11 — see
`docs/architecture/14-TASK-LIFECYCLE.md` for the full diagram and
`docs/phase-4/TASK-STATE-MACHINE.md` for the eight transitions Phase 4's
real runtime surfaced beyond the original Phase 1 design. This page
records the one thing Phase 11 needed to re-verify against that machine:
that real `REPLAN` recovery doesn't require any new transition.

## `RECOVERING -> PLANNING` was already legal

`veyra_contracts.tasks._LEGAL_TRANSITIONS[TaskState.RECOVERING]` already
included `PLANNING` (added when Phase 4's diagram first anticipated
`REPLAN`, even though nothing exercised it for real until Phase 11). No
contract change was needed to implement real replanning — only orchestrator
code. `TaskStateMachine` (`app/services/agent/state_machine.py`) remains
the single place any code in this repository is allowed to mutate
`Task.state`; `_plan_from_intent` (used both by the first plan and by a
replan) transitions exactly the same way regardless of which caller
invoked it.

## Cooperative cancellation and pause — unchanged, re-verified

`request_cancellation`/`request_pause` remain in-memory, process-global
registries keyed by `task_id` (`orchestrator.py`) — justified because the
Local API is the only process that ever runs a task (CLAUDE.md). Phase 11
didn't touch this mechanism; `tests/integration/test_agent_tasks_api.py`'s
existing pause/resume/cancel tests continue to pass unmodified, and the
new REPLAN and browser_task tests exercise the same `_execute_plan` loop
those checks run inside, so a cancellation or pause requested mid-replan
or mid-browser-task is caught by the exact same `_check_cancelled`/
`_check_paused` calls every other plan's steps go through — no new gap.

## Checkpoint/resume semantics — unchanged, re-verified

`resume_after_confirmation`/`resume_after_pause` continue the *same*
remaining plan (persisted as `pending_plan`/`paused_plan` in
`task.result`, filtered to `sequence >= step.sequence`), never
re-executing already-completed steps or replanning from scratch. This is
distinct from — and unaffected by — `REPLAN` recovery, which explicitly
*does* build a brand-new plan (because the old one's step just failed and
retries/re-observation didn't fix it). The two mechanisms don't overlap:
a paused/awaiting-confirmation task was never in `RECOVERING`, and a
`REPLAN`'d task was never paused or waiting on a stored grant.

## `TaskBudget.max_replans` — pre-existing field, now actually enforced end to end

The field existed since Phase 4 (`docs/architecture/14-TASK-LIFECYCLE.md`
§2, `veyra_contracts.tasks.TaskBudget`) but the code path that would have
spent it never ran (the always-fails `REPLAN` stub failed on the *first*
replan attempt, before `LoopBudgetTracker.total_replans` could ever
exceed it in practice). Phase 11 is the first time this bound is
exercised for real — see `docs/agent/RECOVERY.md` §2.
