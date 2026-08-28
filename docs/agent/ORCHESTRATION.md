# Orchestration (Phase 11)

`AgentOrchestrator` (`app/services/agent/orchestrator.py`) is unchanged in
shape from Phase 4/5 (`docs/phase-4/AGENT-ARCHITECTURE.md`,
`docs/phase-5/BARGE-IN.md`): receive → understand → plan → execute
(ACT→OBSERVE→VERIFY) → recover/confirm/wait as needed → terminate. Phase
11 refactored the "turn an understood intent into a plan and either stop
or execute it" logic out of `run()` into a shared `_plan_from_intent`
method, specifically so real replanning (§2 below) could reuse it exactly
rather than duplicating the `AMBIGUOUS`/`CAPABILITY_UNAVAILABLE`/`UNSAFE`/
`INVALID`/`PLANNED` branching a second time.

## 1. No LLM in the planning loop — still true

`TaskPlanner` remains fully deterministic (`docs/phase-4/PLANNER.md`).
Phase 11 did not add an LLM call anywhere in `run()`, `_plan_from_intent`,
or `_recover()`'s `REPLAN` branch — "replanning" here means *re-running
the same deterministic templates against refreshed inputs*, never an LLM
call. `app/services/agent/llm_provider.py`/`providers.py` (Phase 10) exist
as a real, generic HTTP LLM connectivity layer for health-checking
purposes only — they are not wired into the planner, and Phase 11 did not
change that.

## 2. Real `REPLAN` recovery

Before Phase 11, `RecoveryManager.decide()` could legitimately return
`RecoveryStrategy.REPLAN` (a retryable error persisting past
`max_recovery_attempts`, with replan budget still available), but
`AgentOrchestrator._recover`'s handling of that decision was an
always-fails stub — see `docs/phase-4/RECOVERY.md` §3 for the exact
`IllegalTaskTransitionError` bug that stub's first version had.

The real implementation:

```
_recover(): decision.strategy == REPLAN
    │
    ▼
context.replan_count += 1; tracker.record_replan()
    │
    ▼  (LoopBudgetTracker.budget_exceeded_reason(), still checked)
sm.transition(RECOVERING -> PLANNING)      # legal per veyra_contracts
    │
    ▼
intent = StructuredIntent.model_validate(task.normalized_goal)
    │
    ▼
_plan_from_intent(...)   # the exact same code run() uses for the first plan
    │
    ├─ AMBIGUOUS              -> WAITING_USER (clarifying question)
    ├─ CAPABILITY_UNAVAILABLE/UNSAFE/INVALID -> FAILED
    └─ PLANNED                -> EXECUTING -> _execute_plan(new plan)
```

Key properties, all real and tested
(`tests/integration/test_agent_tasks_api.py`):

- **Fresh context, not a blind retry of the same plan.** The planner is
  re-invoked with a freshly-called `search`/`memory_lookup` function
  (`_make_search_fn`/`_make_memory_lookup_fn`), so a replan reflects
  *current* filesystem/memory state — the deterministic templates
  themselves are pure functions of their inputs, so if nothing in the
  environment changed, the new plan is identical to the old one (this is
  expected and correct, not a bug — see the "recovers" test below for the
  case where the environment/tool behavior genuinely differs between
  attempts).
- **Bounded twice over**: `RecoveryManager.decide()` won't choose `REPLAN`
  once `replan_count >= budget.max_replans`, and `LoopBudgetTracker`
  independently re-checks `total_replans > budget.max_replans` before
  every replan attempt — the same "no unbounded loops, ever" discipline
  (CLAUDE.md) as every other recovery strategy.
- **Never a second execution path.** A successful replan hands control to
  the *same* `_execute_plan` every other plan runs through — no
  orchestrator-side shortcut, no bypassed Policy Engine/Tool Registry
  call.
- **Exhausted budget asks the user, never crashes or silently fails.**
  `test_replan_exhausted_asks_user_never_crashes` forces every tool call
  to fail, with `max_recovery_attempts=0` and `max_replans=1`: one real
  replan attempt happens (RecoveryManager's actual bounded escalation
  path, not a mock), fails too, and the task correctly lands at
  `WAITING_USER` with a clarifying question naming the problem.
- **A successful replan actually recovers.** 
  `test_replan_recovers_when_the_replanned_attempt_succeeds` makes the
  first tool call fail and every call after it real (a genuinely
  transient condition), and the task reaches `COMPLETED` through the
  freshly-built plan.

## 3. Observation and verification

Each `PlanStep` carries an optional `verification_strategy` string
(`"process_and_window_detection"`, `"window_state_check"`,
`"page_observation"`, ...) — documentation of *how* a step's outcome
should be checked, consumed by the step's own tool executor and by a
human/future automated reviewer reading `TaskStep.actual_result`; there is
no separate "Verification Engine" class because verification in this
codebase is a property of the tool call's own `ToolResult`
(`ToolResultStatus.SUCCESS`/`FAILURE` + `ErrorInfo`), checked immediately
after each step in `_execute_plan` — never a fabricated "looks done"
judgment. `TaskState.OBSERVING`/`VERIFYING` are real states the task
machine passes through on its way to `COMPLETED` (see
`docs/agent/TASK-LIFECYCLE.md`).

## 4. `WorkflowMemory` alias resolution

`docs/architecture/09-MEMORY.md` §4 specified this contract since Phase 1
("office folder" → `D:\Projects\Office`) but noted "no live planner exists
yet to run it against." Phase 11 wires it in:

```
TaskPlanner._plan_open_file(intent, search, memory_lookup)
    │
    ▼  (memory_lookup is not None)
alias = self._alias_query(intent)   # "my office folder" -> "office folder"
    │
    ▼
resolved_path = await memory_lookup(alias)
    │
    ├─ found  -> _plan_single_file_open(intent, resolved_path)   # no search, no ambiguity
    └─ not found -> falls through to the existing search-based resolution
```

`AgentOrchestrator._make_memory_lookup_fn` is the real implementation:
reads the same `Memory` table `/memory`'s own CRUD API exposes (never a
second, parallel alias store), scoped to the task's user,
`category == MemoryCategory.WORKFLOW`, a case-insensitive exact match on
`key`. This is a deliberate *exact* match — resolving a user-defined
alias they typed verbatim before — never a fuzzy/semantic guess (guessing
between multiple plausible candidates is `resolve_ambiguity`'s job, never
this one's).

Verified: `tests/unit/test_agent_planner.py::
test_open_file_resolves_a_workflow_memory_alias_without_searching` (proves
`search` is never even called when an alias matches — a short-circuit,
not merely a priority order) and `tests/integration/test_agent_tasks_api.py::
test_workflow_memory_alias_resolves_a_real_open_task` (a real `POST
/memory` row, then a real task run, end to end, no fakes).

## 5. `browser_task` planning template

Before Phase 11, every `browser_task` intent was `CAPABILITY_UNAVAILABLE`
by design (Phase 4 brief §64 explicitly excluded building the browser
agent — Phase 8 built it afterward, but nothing re-connected it to the
planner). `TaskPlanner._plan_browser_task` now produces a real, bounded
plan on Phase 8's already-registered browser tools
(`docs/phase-8/BROWSER-TOOLS.md`):

```
always:            browser.launch (headless=False — the user asked to see it)
if a web search
is named:           browser.search (query, engine="google" —
                     browser.search's own supported engines only:
                     google/bing/duckduckgo, never a guessed
                     site-specific search URL)
always:             browser.get_page (verify the page loaded)
```

`_WEB_SEARCH_QUERY_RE` extracts the query from phrasing like "search the
web for X" / "search web X". No confirmation is required (every step is
`RiskLevel.SAFE`), matching `browser.launch`/`browser.search`/
`browser.get_page`'s own tool-level risk tiers.

**Deliberately not implemented**: a multi-step "open Chrome, search
YouTube, click the first video, press play" flow. That would require the
planner to pre-decide a click target (`browser.click`'s `query` argument)
without ever having observed the page — exactly the kind of guess
`docs/phase-4/PLANNER.md`'s "never guesses between ambiguous candidates"
principle and this phase's own "do not overbuild" instruction rule out.
The already-real browser tools (`browser.click`, `browser.find`, etc.)
remain available for such a flow to be driven step by step by a future,
smarter planner or a human — Phase 11 did not remove or weaken that
capability, it only declined to fabricate a preplanned guess on top of it.

Verified: `tests/unit/test_agent_planner.py` (3 tests — with a search
query, without one, and `CAPABILITY_UNAVAILABLE` when browser tools
aren't registered) and `tests/integration/test_agent_tasks_api.py::
test_browser_task_search_completes_for_real` (a real 3-step plan run
through the actual orchestrator/Policy Engine/Tool Registry chain against
the browser tools' `FakeBrowserAdapter`).
