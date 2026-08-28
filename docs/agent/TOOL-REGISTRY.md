# Tool Registry (Phase 11 — unchanged, re-verified)

Phase 11 did not add a new tool registry, a second registration path, or
any bypass around the existing one. This page records what was
re-verified while implementing this phase's three additions (real
`REPLAN`, `WorkflowMemory` aliases, `browser_task` planning) and where the
authoritative docs live.

## The one registry

`app/services/tool_registry.py`'s `ToolRegistry` remains the single
source of truth for every tool this codebase can call — every domain
(`filesystem.*`, `application.*`, `window.*`, `browser.*`, `download.*`,
`web.research`, `system.*` diagnostics, IoT device tools, integration
tools) registers into the same instance at startup
(`app/main.py`'s lifespan, `docs/architecture/04-TOOL-ARCHITECTURE.md`).
`TaskPlanner`'s new `browser_task` template and the pre-existing
`open_application`/`search_files`/`open_file` templates all go through
the exact same `ToolSelector.select(tool_id)` gate
(`docs/phase-4/TOOL-SELECTION.md`) before a step is ever included in a
plan — a tool that isn't registered degrades the template to
`CAPABILITY_UNAVAILABLE`, never a plan step `AgentOrchestrator` would only
reject later. `tests/unit/test_agent_planner.py::
test_browser_task_is_capability_unavailable_without_browser_tools` proves
this holds for the new template too.

## `ToolSelector`'s one job — unchanged

`app/services/agent/tool_selector.py` still does exactly one thing:
reject a tool id that doesn't exist in the registry at all (a
"hallucinated tool"), before ever constructing a `ToolCallRequest` for it.
Argument-shape validation is still not duplicated here — every tool
executor validates its own arguments via a pydantic model, and
`callable_executor` already maps a `ValidationError` to
`TARGET_CONTEXT_REQUIRED`/`VALIDATION_ERROR`. Phase 11 added zero new
tools of its own (the `browser_task` template calls three tools Phase 8
already registered: `browser.launch`, `browser.search`, `browser.get_page`)
and zero new argument-shape logic.

## Dynamic discovery — unchanged

Phase 7's dynamic tool discovery/selection for the planner
(`docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md`) continues to work
unmodified; Phase 11's new `browser_task` template participates in it the
same way every other template does — through `ToolSelector`, not a
side-channel lookup.

## Where the full contract lives

`docs/architecture/04-TOOL-ARCHITECTURE.md` — registration requirements
(`risk_level`, `required_permission`, mandatory `AuditLog` row per call),
`docs/phase-4/TOOL-SELECTION.md` — the planner-facing selection contract,
`docs/phase-8/BROWSER-TOOLS.md` — the specific tools Phase 11's
`browser_task` template plans against.
