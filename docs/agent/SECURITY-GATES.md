# Security Gates (Phase 11 — unchanged, re-verified)

Phase 11's brief was explicit: "DO NOT bypass the security system. DO NOT
give the LLM unrestricted operating-system access. DO NOT allow the model
to directly execute arbitrary shell commands." No code in this phase
touches the Policy Engine, the audit log, or the tool-execution chokepoint
— every new capability (real `REPLAN`, `WorkflowMemory` aliases,
`browser_task` planning) produces plan steps that flow through the exact
same, single, unconditional chain every other tool call in this codebase
uses.

## The one chain — every call, no exceptions

```
AgentOrchestrator._call_tool(tool_id, arguments)
      │
      ▼
execute_tool_call(session, registry, call, user_id)   # app/services/tool_execution.py
      │
      ├─ tool not registered           -> UnknownToolError (never reached — ToolSelector already rejected it)
      ├─ tool disabled                 -> TOOL_DISABLED, AuditLog written, never reaches Policy Engine
      ▼
PolicyEngine.evaluate(session, user_id, tool_id, risk_level, target)
      │
      ├─ SAFE            -> always allowed (still logged; checked, never blocked)
      ├─ CRITICAL         -> never satisfied by ANY stored grant, including ALWAYS_ALLOW
      │                      (docs/security/08-SENSITIVE-ACTION-POLICY.md §2)
      ├─ MODERATE/SENSITIVE -> a matching, unexpired PermissionGrant, or denied
      ▼
executor.execute(call)          # the ONLY place a tool's real side effect happens
      │
      ▼
write_audit_log(...)            # exactly one AuditLog row, success OR failure OR unhandled exception
```

This is unchanged from `docs/security/01-SECURITY-ARCHITECTURE.md`'s core
chain and from the Phase 9 P1-3 fix (guaranteed audit-log-on-crash) — see
`services/local-api/app/services/tool_execution.py`'s own `try`/`except
Exception` around `executor.execute(call)`, which writes the audit row
and re-raises rather than swallowing an unanticipated executor bug.

## What Phase 11's three additions actually do here

- **Real `REPLAN`**: produces a brand-new `ExecutionPlan` from the
  deterministic planner — every step in it is a normal `PlanStep` that
  `_execute_plan` runs through the chain above exactly like a first-attempt
  plan's steps. No new bypass, no direct tool invocation from
  `RecoveryManager` or `_recover()`.
- **`WorkflowMemory` alias resolution**: only changes which *path string*
  ends up as a `filesystem.open` step's `path` argument — it is still a
  normal `filesystem.open` call, still policy-checked (the Policy Engine
  doesn't distinguish "planner found this by searching" from "planner
  found this via a memory alias"; both produce the same `ToolCallRequest`
  shape) and still audit-logged. `_make_memory_lookup_fn` performs a
  read-only `select()` against the `Memory` table — no write, no
  side effect, no privilege change.
- **`browser_task` planning**: the three tools it plans
  (`browser.launch`/`browser.search`/`browser.get_page`) are all
  pre-existing, `RiskLevel.SAFE` Phase 8 tools, already reviewed under
  `docs/phase-8/BROWSER-TOOLS.md`'s own security model (CAPTCHA/OTP/
  payment stop conditions, URL validation, prompt-injection tagging on
  extracted text). Phase 11 added no new browser tool and no new
  risk tier — it only decided, deterministically, when to include these
  specific existing tools in a plan.

## No LLM in this loop — still true, still checked

`TaskPlanner` remains fully deterministic; there is still no code path
from a model's output to a `ToolCallRequest` (`docs/architecture/
03-AI-ARCHITECTURE.md` §6, unchanged). `tests/security/
test_agent_adversarial.py` (hallucinated-tool rejection, fake-success
never overriding a real failure, infinite-retry bounded by budget,
mid-plan cancellation, a MODERATE action without a grant denied not
executed) and `tests/security/test_phase5_voice_security.py`'s 12
adversarial voice scenarios all re-ran unmodified against this phase's
changes (after fixing their `fake_plan` test doubles' call signature to
accept the new `memory_lookup` keyword — a test-only change, not a
security-relevant one) and pass.

## No new shell/OS access

Neither `_plan_from_intent`, `_make_memory_lookup_fn`, nor
`_plan_browser_task` calls `subprocess`, `os.system`, or any shell/
PowerShell invocation — `_make_memory_lookup_fn` is a single SQLAlchemy
`select()`; everything else composes existing, already-reviewed
`ToolCallRequest`s. `tests/security/test_no_unrestricted_shell.py`
(repo-wide grep for disallowed subprocess/shell patterns) re-ran clean.
