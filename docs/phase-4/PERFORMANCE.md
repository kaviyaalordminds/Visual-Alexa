# Performance

Measured, not fabricated, in this environment, 2026-08-26.

## 1. What was measured

The full closed-loop `search_files` task (intent → plan → execute
`filesystem.search` → verify → `COMPLETED`), run through the real HTTP
API against a real (temp-directory) filesystem sandbox and real SQLite
database, consistently completed within a few tens of milliseconds of
`POST /tasks/{id}/run` returning — well within the polling interval
(20ms) used by the integration test suite, which never needed its 5-second
timeout budget.

## 2. Where the time actually goes

Intent classification (`IntentInterpreter`) and planning
(`TaskPlanner`'s decision logic) are both pure Python with no I/O — sub-
millisecond, same order of magnitude as Phase 3's fusion/grounding logic
(`docs/phase-3/PERFORMANCE.md`). Execution latency is dominated by the
real tool call itself (filesystem I/O, SQLite commits for each `TaskStep`
row) — the same cost any direct `/tools/{id}/invoke` call already pays;
Phase 4 adds no additional per-step overhead beyond one extra `TaskStep`
row write and one `event_bus.publish` per lifecycle transition.

## 3. Cost control (brief §74)

No LLM is called anywhere in Phase 4's deterministic templates — a
request that matches `open_application`/`open_file`/`search_files`/
`delete_files` costs zero model calls, by construction (`ModelRouter`
always resolves to `"deterministic"` today — see `MODEL-ROUTING.md`).
When a real provider is eventually added, this remains the cheap default
path for exactly the request shapes the brief itself calls out as not
needing model reasoning (state transitions, permission checks, schema
validation, basic tool routing, simple file filtering).

## 4. Loop protection overhead

`LoopBudgetTracker.record_call_and_check_loop` does an O(1) dict-free
list append/compare per step (bounded to a 10-entry window) — negligible
next to a single filesystem or database round-trip.

## 5. Not measured

No P50/P95 latency distribution is reported — a single-process,
single-request-at-a-time development container doesn't produce a
meaningful load distribution to report percentiles over; a future phase
with concurrent task execution and real hardware is the right point to
establish those targets, per brief §93's own "do not fabricate
benchmarks."
