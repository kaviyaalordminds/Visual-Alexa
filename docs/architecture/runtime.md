# VEYRA Runtime

Phase 13's spec asked for a central `VeyraRuntime` composing an
InputManager/ContextManager/Planner/PermissionManager/ToolRegistry/
ToolExecutor/Observer/Verifier/RecoveryManager/MemoryManager/
AuditLogger/EventPublisher. Per this repo's own audit discipline
(`docs/phase-13-audit.md`), that composition already exists — as a set
of real, separately-tested collaborators wired together at process
startup, not a single monolithic class. This document names the actual
pieces and where each one lives, so "VeyraRuntime" in any future spec
can be read as "this set of components," not a missing subsystem.

| Role (Phase 13 name) | Real component | Location |
|---|---|---|
| Planner | `IntentInterpreter` + `TaskPlanner` | `app/services/agent/intent.py`, `planner.py` |
| PermissionManager | `PolicyEngine` + `ConfirmationManager` | `app/services/agent/policy.py`, `confirmation.py` |
| ToolRegistry | `ToolRegistry` (process-global singleton) | `app/services/tool_registry.py` |
| ToolExecutor | `execute_tool_call` (the one chokepoint) | `app/services/tool_execution.py` |
| Observer | `TaskContext` + step observation recording | `app/services/agent/context.py`, `orchestrator.py` |
| Verifier | Per-tool `VerificationOutcome` on `ActionResult` | `computer_control`/`vision`/`browser` tool modules |
| RecoveryManager | `RecoveryManager.decide()` | `app/services/agent/recovery.py` |
| MemoryManager | `MemoryService` + `WorkflowMemory` | `app/services/memory.py` |
| AuditLogger | `write_audit_log` | `app/services/audit.py` |
| EventPublisher | `EventBus` (`event_bus.publish_type`) | `app/core/event_bus.py` |
| ContextManager | Per-run `TaskContext` | `app/services/agent/context.py` |
| Orchestration loop | `AgentOrchestrator` | `app/services/agent/orchestrator.py` |

`AgentOrchestrator` is the actual runtime entry point: it owns one
instance of each collaborator above and drives the state machine
described in `14-TASK-LIFECYCLE.md` and `task-execution.md` (this
directory). Every tool call — whether triggered by the orchestrator or
invoked directly via `POST /tools/{id}/invoke` — passes through the same
`execute_tool_call` function, so there is exactly one path from "a tool
should run" to "a tool ran": Policy Engine → Tool Registry → Executor →
Audit Log → Event Bus. No second, faster path exists or is permitted
(`CLAUDE.md` — "never bypass security").

## What Phase 13 added to this runtime

Three real, bounded fixes to how these components integrate, not new
components:

1. **Idempotent step retries.** `AgentOrchestrator._step_call_id(task_id,
   sequence)` produces a stable `call_id` reused across
   `RecoveryManager.RETRY` attempts of the same step.
   `execute_tool_call` keeps a bounded, TTL'd cache
   (`_idempotency_cache`) keyed by `call_id` and returns the cached
   result instead of re-invoking the executor — but only for a prior
   *success*; a genuine failure is never cached, so `RecoveryManager`'s
   retry logic still genuinely retries. See `docs/phase-13-audit.md §4`.
2. **Real correlation IDs on log lines.** `execute_tool_call` now calls
   `set_correlation_id`/`reset_correlation_id` (a `contextvars.Token`-
   based scope, restored via `try/finally`) around every tool call, and
   `JSONFormatter` (`app/core/logging.py`) now includes arbitrary
   structured `extra` fields instead of silently dropping them. This
   closed a real, silent gap: the event-bus `correlation_id` was always
   real, but the log-line one was always `null` in practice
   (`docs/phase-13-audit.md §5`).
3. **`SYSTEM_HEALTH_CHANGED` is now actually published.** `GET /system`
   (`app/api/system.py`) diffs each computed status snapshot against the
   previous one and publishes only the fields that changed — the event
   type existed since Phase 1 but nothing ever called it.

## Non-negotiables this runtime enforces

- The Policy Engine check in `execute_tool_call` is unconditional —
  there is no tool-call path that skips it, including retries and
  idempotent replays (a cached result was already policy-checked on its
  original execution).
- CRITICAL-risk actions never resolve from a cached idempotency result
  or a stored grant — see `docs/security/permissions.md`.
- Every tool call writes exactly one `AuditLog` row, success or failure,
  via the same `write_audit_log` call inside `execute_tool_call`.
