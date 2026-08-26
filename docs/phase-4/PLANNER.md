# Planner

`TaskPlanner` (`app/services/agent/planner.py`) — `StructuredIntent` →
`ExecutionPlan`. Deterministic templates, not the "final AI planner" —
see `PHASE-4-IMPLEMENTATION-PLAN.md` §8 for the exact, explicit scope.

## 1. Templates

- **`open_application`** — `application.launch` + `window.get_active`
  (verify). No search needed; an unknown app name surfaces as
  `APPLICATION_NOT_FOUND` at execution time (`RecoveryManager` treats it
  as permanent, no retry).
- **`search_files`** — one `filesystem.search` step per configured
  allowed root (SAFE, no confirmation).
- **`open_file`** — searches all roots (via an injected `SearchFn`, see
  §2), filters by extension/time constraint, then either:
  - `ordering: "latest"` given explicitly → picks the most recently
    modified candidate deterministically, no question asked (Final
    Acceptance Test #2's shape).
  - Otherwise → `veyra_contracts.resolve_ambiguity` over the candidates
    — 0 or 1 candidate resolves silently; 2+ returns `AMBIGUOUS_TARGET`-
    equivalent (`PlanOutcome.status == "AMBIGUOUS"`) with every
    candidate's label in the clarifying question, matching the exact
    ambiguity contract Phase 1 already built and tested
    (`tests/agent-evals/test_ambiguity_fixture.py`) — never a guess.
- **`delete_files`** — always `CAPABILITY_UNAVAILABLE`, honestly, since
  Phase 2 deliberately has no delete tool. Still runs the search (when a
  `SearchFn` is available) to report *how many* files and their total
  size would have been affected — the brief's own preview spirit (§49),
  without pretending the deletion itself is possible.
- **`send_file`, `control_device`, `browser_task`** — `CAPABILITY_UNAVAILABLE`
  immediately, no search, no network scan, no device discovery.

## 2. Dependency injection keeps this testable without a real filesystem

`SearchFn = Callable[[str, str | None], Awaitable[list[FileCandidate]]]`
is injected per call. `AgentOrchestrator` supplies a real implementation
(`_make_search_fn`) that calls `filesystem.search` through
`execute_tool_call` — the real Policy-Engine-gated path. Unit tests
(`tests/unit/test_agent_planner.py`, 12 tests) supply a fake returning
canned candidates, so the planner's *decision logic* — which template,
how ambiguity is resolved, what counts as a match — is fully verified
without any I/O at all.

## 3. `ToolSelector` gate

Every template calls `ToolSelector.select(tool_id)` before including a
step — if the tool isn't registered (a differently-configured
deployment, a disabled tool), the template degrades to
`CAPABILITY_UNAVAILABLE` rather than producing a plan step
`AgentOrchestrator` would only reject later. See `TOOL-SELECTION.md`.

## 4. Verified

12 unit tests (fake registry + fake search) plus every template exercised
end-to-end for real in `tests/integration/test_agent_tasks_api.py`
against the actual filesystem sandbox and Tool Registry.
