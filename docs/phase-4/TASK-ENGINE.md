# Task Engine

## 1. `Task` / `TaskStep` — extended, not duplicated

Phase 1's `Task`/`TaskStep` tables (`app/models/task.py`) are extended
additively (migration `de808f46a925`) rather than replaced. See
`PHASE-4-IMPLEMENTATION-PLAN.md` §9 for the exact column list and the
`extra_metadata`-not-`metadata` naming note (SQLAlchemy reserves
`metadata` on declarative models).

## 2. `TaskBudget` — the mandatory guardrail

`veyra_contracts.TaskBudget` (`max_steps`, `timeout_seconds`,
`max_recovery_attempts`, `max_replans` — the last added in Phase 4 with a
default so Phase 1 callers are unaffected). Every task carries one;
`POST /tasks` still 422s without it (Phase 1 behavior, unchanged, still
tested).

## 3. `LoopBudgetTracker` — CLAUDE.md's 'no unbounded loops, ever'

`app/services/agent/loop_protection.py`. One instance per `AgentOrchestrator.run`
call, tracking: steps executed, elapsed wall time, total replans, and
identical-`(tool_id, arguments)`-repeated-3× loop detection. Any of these
firing routes the task to `TaskState.TIMED_OUT` — see
`TASK-STATE-MACHINE.md`. Fully unit-tested
(`tests/unit/test_agent_loop_protection.py`), including the loop-detection
case (repeating the exact same call 3× is flagged; the same tool with
different arguments, e.g. searching multiple roots, is not).

## 4. Task API (`app/api/tasks.py`)

| Endpoint | Purpose |
|---|---|
| `POST /tasks` | Create (Phase 1, unchanged) |
| `GET /tasks`, `GET /tasks/{id}` | List/read (Phase 1, unchanged) |
| `GET /tasks/{id}/steps` | New — per-step progress |
| `POST /tasks/{id}/run` | New — starts the orchestrator as a background task, returns 202 |
| `POST /tasks/{id}/cancel` | New — cooperative stop signal |
| `POST /tasks/{id}/confirm` | New — grants the pending step's permission and resumes |

`run`/`confirm` both execute in a real background `asyncio.Task` (tracked
in a module-level set so it isn't garbage-collected mid-flight — see
`ruff`'s `RUF006`), each opening its own DB session
(`app/db/session.SessionLocal`), since the triggering HTTP request's
session closes once the response is sent. A client polls `GET /tasks/{id}`
for progress — this is the concrete implementation of brief §29's
"Step 3 of 7: Searching Downloads folder" progress model
(`current_step`/`total_steps` on the `Task` row).

## 5. Simulation / dry-run (brief §49-50)

Not separately implemented as a standalone mode in Phase 4: every planned
step through the real templates (`open_application`, `search_files`,
`open_file`) is already SAFE-risk, and `delete_files` never reaches
execution at all (`CAPABILITY_UNAVAILABLE` — see `PLANNER.md`), so the
brief's own dry-run example is naturally satisfied by the planner's
honesty rather than a separate simulation flag. A true "preview without
executing" mode for a future MODERATE+ template is a documented gap — see
`PHASE-4-TEST-RESULTS.md` known limitations.

## 6. Task replay (brief §51)

Not implemented. Every `TaskStep` row already records `tool_id`,
`arguments`, `actual_result`, and `error` — sufficient raw material for a
future replay framework to build from without Phase 4 needing to design
one against no real consumer yet, the same "don't design a schema against
a hypothetical consumer" judgment already applied in
`docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md` §7.
