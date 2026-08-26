# 04 — Tool Architecture

## 1. Principle

The LLM never directly controls the operating system. It can only request
execution of a **registered tool** with schema-validated arguments. This is
the single most important architectural boundary in VEYRA — see
`CLAUDE.md` and `docs/security/01-SECURITY-ARCHITECTURE.md`.

## 2. Core types (`packages/contracts`)

```
ToolDefinition
  id: str                     # stable, namespaced e.g. "filesystem.search"
  name: str
  description: str
  category: ToolCategory      # filesystem | windows | process | screen |
                               # keyboard | mouse | browser | communication |
                               # media | documents | system | iot
  input_schema: JSONSchema
  output_schema: JSONSchema
  risk_level: RiskLevel       # SAFE | MODERATE | SENSITIVE | CRITICAL
  required_permission: str    # permission scope key
  confirmation_policy: ConfirmationPolicy  # NEVER | SESSION | ALWAYS
  timeout_seconds: int
  cancellable: bool
  verification_strategy: VerificationStrategy
  audit_metadata: dict

ToolExecutor (interface)
  execute(call: ToolCallRequest) -> ToolResult

ToolResult
  call_id: str
  status: ToolResultStatus    # SUCCESS | FAILURE | TIMEOUT | CANCELLED
  output: dict | None
  error: ErrorInfo | None     # see 07-ERROR-MODEL section in security docs
  evidence_tier_used: EvidenceTier | None
  duration_ms: int

ToolRegistry
  register(definition: ToolDefinition, executor: ToolExecutor)
  get(tool_id: str) -> ToolDefinition
  list(category: ToolCategory | None) -> list[ToolDefinition]

ToolVerifier (interface)
  verify(call: ToolCallRequest, result: ToolResult) -> VerificationOutcome
```

## 3. Execution path

```
ToolCallRequest (from planner)
        │
        ▼
Policy Engine  ── rejects if no valid PermissionGrant for
        │           (tool_id, target, risk_level)
        ▼
ToolRegistry.get(tool_id)  ── rejects unknown tool IDs
        │
        ▼
ToolExecutor.execute()  ── Phase 1: NotImplementedStub for every tool
        │
        ▼
ToolVerifier.verify()  ── confirms expected postcondition, not just
        │                  "did the call not throw"
        ▼
AuditLog.write()  ── always, success or failure
        │
        ▼
EventBus.publish(task.progress / tool.executed)
```

## 4. Risk levels drive behavior, not just documentation

`risk_level` is read by the Policy Engine at runtime to decide whether a
`PermissionGrant` is required and whether confirmation is mandatory
(`CRITICAL` always requires confirmation regardless of any stored grant —
see `docs/security/08-SENSITIVE-ACTION-POLICY.md`). It is not merely a label.

## 5. Phase 1 tool categories (defined, not implemented)

`filesystem`, `windows`, `process`, `screen`, `keyboard`, `mouse`,
`browser`, `communication`, `media`, `documents`, `system`, `iot` — all
represented as an enum in `packages/contracts`. Zero concrete tools are
registered with real executors in Phase 1; the registry ships with example
`SAFE`-tier stub definitions (e.g., `system.get_status`) whose executor
returns static/DB-backed data, specifically so the registry → policy →
executor → verify → audit path is exercised end-to-end by tests without
performing any real OS action.

## 6. What must NOT change without architectural review

- No tool executor may call `subprocess`, `os.system`, PowerShell, or any
  shell invocation with unvalidated/model-originated input.
- No tool may be registered without a `risk_level` and
  `required_permission`.
- The Policy Engine check must remain unconditionally in the execution path
  for every tool, including `SAFE`-tier ones (SAFE tools still get a
  permission check against a default-granted SAFE-tier policy — they are
  not exempt from the code path, only from requiring user confirmation).
