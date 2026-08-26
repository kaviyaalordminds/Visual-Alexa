# Audit

## 1. Two complementary trails, not a duplicated one

- **`AuditLog`** (Phase 1, `app/services/audit.py`) — one row per tool
  call, unchanged. Every `PlanStep` execution goes through
  `execute_tool_call`, so it already writes exactly one row, success or
  failure, exactly as before Phase 4 existed.
- **`EventType.TASK_*` events** (new in Phase 4, via the existing Phase 1
  `event_bus`) — task-level lifecycle: `TASK_CREATED`, `TASK_PLANNED`,
  `TASK_STEP_STARTED`/`_COMPLETED`/`_FAILED`, `TASK_CONFIRMATION_REQUIRED`/
  `_RECEIVED`, `TASK_RECOVERY_STARTED`/`_COMPLETED`, `TASK_CANCELLED`,
  `TASK_FAILED`, `TASK_TIMED_OUT`. These are ephemeral pub/sub events (a
  future UI subscribes for live progress), not a persistence mechanism —
  the durable record is still `AuditLog` + `TaskStep` rows.

## 2. Never logs secrets

`write_audit_log`'s existing `_SENSITIVE_KEYS` redaction
(`password`/`secret`/`token`/`otp`/`credential`) applies unchanged to
every `PlanStep.arguments` dict passed through `execute_tool_call` — Phase
4 introduces no new argument shapes that bypass it.

## 3. Append-only (brief §53)

Nothing in `app/services/agent/` ever updates or deletes an `AuditLog`
row — `write_audit_log` only ever `session.add()`s. There is no AI tool
or orchestrator code path with delete/update access to the `audit_logs`
table at all (SQLAlchemy models expose no such method, and no route in
`app/api/` accepts one).

## 4. Full trail for one task

`GET /tasks/{id}/steps` (new) plus the existing audit query surface give
a complete reconstruction: what was planned (`TaskStep.description`/
`arguments`), what actually ran (`AuditLog.tool_id`/`request_payload_summary`),
what happened (`AuditLog.result_status`/`error_code`, `TaskStep.actual_result`/
`error`), and the task-level narrative (`Task.state`, `failure_reason`,
`result`).
