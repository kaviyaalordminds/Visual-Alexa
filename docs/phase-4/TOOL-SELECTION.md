# Tool Selection

`ToolSelector` (`app/services/agent/tool_selector.py`) — brief §16/§77:
"do not allow the model to invent a tool."

## 1. One job

`select(tool_id)` looks up `tool_id` in the real, live `ToolRegistry`
(the exact same registry `/tools/{id}/invoke` uses). Not found →
`UnknownToolSelectedError` (carries `ErrorCategory.UNKNOWN_TOOL`).
`exists(tool_id)` is the non-raising check `TaskPlanner` uses to decide
whether a template is even usable in the current deployment.

## 2. Argument validation is deliberately not duplicated here

Every tool executor already validates its own arguments via a pydantic
model (`_LaunchArgs`, `SearchCriteria`, etc. — see
`docs/architecture/04-TOOL-ARCHITECTURE.md`) and `callable_executor`
already maps a `ValidationError` to a structured error. `ToolSelector`
answers exactly one question — "does this tool exist at all" — and
nothing more, avoiding a second, parallel validation layer that could
drift from the real one.

## 3. Where it's enforced

`TaskPlanner` calls it while building a plan (a template referencing a
tool that isn't registered degrades to `CAPABILITY_UNAVAILABLE` before
any step is ever created). `AgentOrchestrator._call_tool` calls
`ToolSelector.exists` again immediately before invoking `execute_tool_call`
— a second, redundant check by design: even a hand-crafted `ExecutionPlan`
(e.g. from a future replanning path, or a test) naming a nonexistent tool
is caught structurally, never executed, and the task fails with
`UNKNOWN_TOOL` rather than an unhandled `LookupError` propagating out of
the orchestrator.

## 4. Verified

`tests/unit/test_agent_tool_selector.py` (3 tests) plus
`tests/security/test_agent_adversarial.py::test_hallucinated_tool_is_rejected_never_executed`
— a synthetic plan naming `teleport_to_file` is rejected end-to-end
through the real API, `FAILED` with `error.code == "UNKNOWN_TOOL"`, and
no tool call of any kind was ever attempted.
