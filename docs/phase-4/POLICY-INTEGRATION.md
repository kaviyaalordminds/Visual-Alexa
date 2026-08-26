# Policy Integration

## 1. The central decision (see `PHASE-4-IMPLEMENTATION-PLAN.md` §6)

A `PlanStep`'s execution *is* a `ToolCallRequest`, submitted to
`app/services/tool_execution.execute_tool_call` — the identical function
every other tool call in this codebase goes through, including manual
`/tools/{id}/invoke` calls. `AgentOrchestrator` contains **zero**
risk-tier or permission-matching logic of its own.

## 2. What this buys, concretely

- **Policy evaluation**: SAFE always allowed, CRITICAL never
  pre-authorized by any stored grant — the exact same
  `PolicyEngine.evaluate` Phase 1 built and tested, unmodified.
- **Confirmation**: if `execute_tool_call` returns `PERMISSION_DENIED`
  with `user_action_required=True`, the orchestrator transitions to
  `WAITING_PERMISSION` and stops — `ConfirmationManager` only builds the
  human-readable prompt text, it does not decide *whether* to pause.
- **Audit**: every step still writes exactly one `AuditLog` row, success
  or failure — unmodified from Phase 1's contract, redaction included.
- **Resuming**: `POST /tasks/{id}/confirm` creates a real, time-limited
  `PermissionGrant` (via the same `app/models/tool.PermissionGrant` row
  the `/permissions` API uses) and re-submits the identical
  `ToolCallRequest` — it now succeeds because a matching grant exists,
  not because the orchestrator special-cased anything.

## 3. Never bypassable

There is no code path in `app/services/agent/*` that constructs an
`ActionResult`/`ToolResult` directly, calls a tool executor's `.execute()`
without going through `execute_tool_call`, or checks `PermissionGrant`
rows itself. Verified structurally (grep — no such call exists) and
behaviorally (`tests/security/test_agent_adversarial.py::test_moderate_action_without_grant_is_denied_not_executed`
— a MODERATE step with no grant pauses at `WAITING_PERMISSION`, the
filesystem effect never happens).

## 4. Confirmation grant scope

The grant `POST /tasks/{id}/confirm` creates is scoped to the exact
`tool_id`/`target` the paused step needs, time-limited (300s TTL — brief
§22 "time-limited"), and created with whatever `PermissionDecision` the
caller passes (`ALLOW_ONCE` by default) — never a broader grant than the
one action being approved.
