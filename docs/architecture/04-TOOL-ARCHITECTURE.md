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
ToolExecutor.execute()  ── real for filesystem/keyboard/mouse/screen/
        │                  application/window/ui tools since Phase 2;
        │                  platform-unsupported executor on non-Windows
        │                  hosts for the Windows-only ones
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

## 5. Tool categories (Phase 1 defined; `filesystem`/`windows`/`process`/
`screen`/`keyboard`/`mouse` implemented in Phase 2; `vision` added and
implemented in Phase 3)

`filesystem`, `windows`, `process`, `screen`, `keyboard`, `mouse`,
`vision`, `browser`, `communication`, `media`, `documents`, `system`,
`iot` — all represented as an enum in `packages/contracts`. Phase 1
shipped one `SAFE`-tier stub (`system.get_status`) to prove the registry →
policy → executor → verify → audit path end-to-end without performing any
real OS action. **Phase 2** (`docs/phase-2/COMPUTER-CONTROL-DESIGN.md`)
registers 40 real tools across `application`/`window`/`filesystem`/
`keyboard`/`mouse`/`screen`/`ui` — the `filesystem`, `keyboard`, `mouse`,
and `screen` categories are genuinely cross-platform and verified in every
deployment environment; `windows`/`process`-adjacent capabilities
(application/window control, UI Automation) are real, reviewed
Windows-only implementations, gated behind platform-capability detection
so they fail honestly (`PLATFORM_NOT_SUPPORTED`) rather than crash on
non-Windows hosts — see `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2
for why this environment cannot runtime-verify the Windows-only paths.
**Phase 3** (`docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md` §6) adds the
`vision` category and 9 new tools (`screen.capture_region`,
`screen.observe`, `ui.get_tree`, `ui.find_all`, `ocr.extract`,
`vision.analyze`, `vision.locate`, `scene.diff`, `target.ground`) through
the identical registry/policy path — see
`docs/phase-3/VISUAL-PERCEPTION-ARCHITECTURE.md` §3. `browser`,
`communication`, `media`, `documents`, `iot` remain unimplemented, out of
Phase 3 scope.

## 6. What must NOT change without architectural review

- No tool executor may call `subprocess`, `os.system`, PowerShell, or any
  shell invocation with unvalidated/model-originated input. The sole
  Phase 2 exception (`application.launch`'s process spawn and
  `filesystem.open`'s non-Windows fallback) uses only registry-resolved,
  list-argv, `shell=False` calls — reviewed, allowlisted, and statically
  verified by `tests/security/test_subprocess_argv_safety.py`; this is
  not a relaxation of the rule, see
  `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §5.
- No tool may be registered without a `risk_level` and
  `required_permission`.
- The Policy Engine check must remain unconditionally in the execution path
  for every tool, including `SAFE`-tier ones (SAFE tools still get a
  permission check against a default-granted SAFE-tier policy — they are
  not exempt from the code path, only from requiring user confirmation).
