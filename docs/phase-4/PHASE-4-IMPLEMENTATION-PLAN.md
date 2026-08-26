# Phase 4 Implementation Plan — AI Brain, Planner & Task Execution Engine

Written before substantial implementation, per the Phase 4 brief §0.
Records what Phase 1-3 actually built (re-verified, not assumed), where
this phase's suggested design reuses vs. adapts it, and the decisions
made with rationale — same discipline as `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md`
and `docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md`.

## 1. What Phase 1-3 actually implemented (repository inspection findings)

- **A full task lifecycle contract already exists and is real, not just
  documented**: `veyra_contracts.enums.TaskState` (`RECEIVED`,
  `UNDERSTANDING`, `PLANNING`, `WAITING_PERMISSION`, `EXECUTING`,
  `OBSERVING`, `VERIFYING`, `RECOVERING`, `WAITING_USER`, `COMPLETED`,
  `FAILED`, `CANCELLED`) plus `veyra_contracts.tasks.is_legal_transition`
  (a real, unit-tested transition table) and `TaskBudget`
  (`max_steps`/`timeout_seconds`/`max_recovery_attempts`, all bounded —
  CLAUDE.md "no unbounded loops, ever"). **Phase 4 reuses this state
  machine directly** rather than inventing a parallel one. The brief's
  own state names map onto it almost 1:1: `CREATED`→`RECEIVED`,
  `AWAITING_CONFIRMATION`→`WAITING_PERMISSION`,
  `WAITING_FOR_USER`→`WAITING_USER`. Kept as-is rather than renamed, to
  avoid breaking Phase 1's already-tested transition table and the
  `/tasks` API's existing `TaskState` values. One genuine gap: no
  distinct terminal state exists for "budget exhausted" (it currently
  folds into `FAILED`) — added additively as `TaskState.TIMED_OUT`. No
  separate `VALIDATING` state was added: plan validation is a sub-step
  performed while still in `PLANNING`, before the existing
  `PLANNING`→`WAITING_PERMISSION` transition, not a new persisted state —
  this is a deliberate simplification, not an oversight (see §5).
- **`Task`/`TaskStep` database tables and a `/tasks` API already exist**
  (`app/models/task.py`, `app/api/tasks.py`), created in Phase 1, but
  intentionally minimal — "No live Task Runtime advances a task past
  `RECEIVED` in Phase 1 (no planner/executor exists yet)." **Phase 4
  extends these tables additively** (new columns, one Alembic migration —
  same pattern as Phase 2's `Application` table extension) rather than
  creating parallel `task_v2`/`agent_task` tables, per brief §81's own
  "do not duplicate existing tables."
- **The ambiguity contract already exists and is real**:
  `veyra_contracts.ambiguity.resolve_ambiguity`/`AmbiguityCandidate`/
  `AmbiguityResolution`, with a worked fixture
  (`tests/agent-evals/test_ambiguity_fixture.py`) proving "never guess
  between two Aruns." **Phase 4's `IntentInterpreter`/`TaskPlanner` call
  this directly** for any entity resolution — not a new mechanism.
- **`AIProvider`/`PlannedAction` are documented in
  `docs/architecture/03-AI-ARCHITECTURE.md` but do NOT exist in code** —
  verified by grep across `packages/contracts` and `services/local-api`:
  zero matches. This is exactly the brief §0 warning ("do not assume
  previous phases are complete simply because documentation says they
  are") borne out for real. Phase 4 builds the actual `LLMProvider`
  abstraction from scratch, informed by but not bound to that doc's
  unbuilt sketch — see §4.
- **The Tool Registry / Policy Engine / audit pipeline is unchanged since
  Phase 2/3** and is still the only execution path
  (`app/services/tool_execution.execute_tool_call`). **Phase 4's
  `AgentOrchestrator` calls this exact function for every planned step**
  — it does not reimplement policy evaluation, permission checking, or
  audit logging. This is the single most important reuse decision in
  this phase (see §6): a task step *is* a `ToolCallRequest`, submitted
  through the identical chain a human-triggered `/tools/{id}/invoke` call
  already goes through.
- **Confirmation already has a real, working mechanism**: the Policy
  Engine's `PolicyDecision(allowed=False, requires_confirmation=True)`
  plus the existing `/permissions` `PermissionGrant` API
  (`docs/security/08-SENSITIVE-ACTION-POLICY.md`). Phase 4's
  `ConfirmationManager` builds specific, understandable confirmation
  text on top of this, it does not replace it.
- **`ContentSource`/`TRUSTED_CONTENT_SOURCES` already exist** (added in
  Phase 3, `packages/contracts/python/veyra_contracts/enums.py`) and
  already encode exactly the brief §38 trust model (`USER`/`USER_INPUT`/
  `SYSTEM`/`SYSTEM_STATE` trusted; `UI_OBSERVATION`/`WEB_CONTENT`/
  `DOCUMENT_CONTENT`/`TOOL_RESULT`/`AI_OUTPUT` untrusted). **Phase 4 reuses
  this set unchanged** — the brief's §38 names (`USER_INSTRUCTION`,
  `SYSTEM_INSTRUCTION`, `MODEL_OUTPUT`) are aliases for values that
  already exist under slightly different names (`USER_INPUT`, `SYSTEM_STATE`,
  `AI_OUTPUT`); adding a second, parallel enum would fragment the one
  place "which sources may authorize an action" is decided, which Phase
  3 built specifically to be that one place.
- **Phase 3's perception tools are real and callable**: `screen.observe`,
  `target.ground`, `ui.get_tree`, `scene.diff`, etc., all registered
  through the same Tool Registry. **Phase 4's verification step calls
  these as ordinary tool calls** (per brief §61 — "Phase 4 must request
  `screen.observe`/`ui.find`/`scene.diff`... rather than implementing its
  own screenshot/OCR system"), never importing `vision`/`computer_control`
  directly for perception.
- **`ErrorCategory` (`veyra_contracts.enums`) already covers ~90% of the
  brief's §47 failure taxonomy** under existing names (`UI_NOT_FOUND`≈
  `TARGET_NOT_FOUND`, `APPLICATION_NOT_FOUND`≈`APP_NOT_FOUND`,
  `APPLICATION_LAUNCH_FAILED`≈`APP_FAILED_TO_START`, `TOOL_FAILURE`≈
  `TOOL_FAILED`, `OPERATION_CANCELLED`≈`USER_CANCELLED`, `MODEL_FAILURE`≈
  `MODEL_ERROR`, etc.). **Phase 4 extends `ErrorCategory` additively**
  with exactly the values it doesn't already have
  (`AMBIGUOUS_TARGET`, `STATE_MISMATCH`, `RESOURCE_BUSY`, `INVALID_PLAN`,
  `UNKNOWN_TOOL`) rather than introducing a second, parallel
  "FailureCategory" enum — the brief's list and the existing enum
  describe the same concept (why a call failed) at the same granularity;
  keeping one enum keeps "is this retryable" (`RETRYABLE_CATEGORIES`,
  `packages/contracts/python/veyra_contracts/errors.py`, already exists
  from Phase 1) a single source of truth instead of two.
- **Environment constraint, restated**: still Linux, not Windows
  (`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2 applies unchanged).
  Phase 4's orchestration/state-machine/planning logic is pure Python and
  fully verifiable here; the Windows-only *tools* it calls (via Phase 2/3)
  are exercised against the same fakes those phases already built
  (`computer_control.testing`, `vision.testing`).

## 2. The central technical decision: no new top-level package

Unlike Phase 2 (`services/computer-control`) and Phase 3 (`services/vision`),
**Phase 4 does not create a new installable package.** Both prior
packages needed to be separate because they contain capability code that
is conceptually reusable outside the API process (OS control, perception)
and Phase 3 explicitly depends on Phase 2's package. The `AgentOrchestrator`
is different in kind: it requires direct, transactional database access
to `Task`/`TaskStep` rows, and CLAUDE.md is explicit that "the Local API
is the only process with database access." There is nothing for a
separate `veyra-agent` package to be independent *of* — it is Local-API
logic, so it lives in `services/local-api/app/services/agent/`, exactly
where Phase 1's `tool_registry`/`policy_engine`/`tool_execution` already
live. Pure, shareable *data contracts* (not behavior) that describe a
plan/intent still go in `packages/contracts` — same rule Phase 1-3 always
followed: contracts hold typed shapes, service packages hold behavior.

## 3. What's genuinely testable here (same discipline as Phase 2/3)

| Capability | Verified here? |
|---|---|
| Task state machine (extended) | **Yes** — pure Python, already partially tested in Phase 1, extended tests added |
| `IntentInterpreter` (deterministic, rule-based) | **Yes** — pure Python, no model dependency at all |
| `TaskPlanner` + `ToolSelector` | **Yes** — pure Python, validated against the real Tool Registry |
| `ConfirmationManager` | **Yes** — real Policy Engine integration, real HTTP round-trip |
| `RecoveryManager` | **Yes** — pure Python decision logic, exercised against synthetic failures |
| `ContextManager` / `TaskContext` summarization | **Yes** — pure Python |
| Loop protection (`max_steps`/`max_retries`/`max_replans`/timeout/loop detection) | **Yes** — deterministic, exercised with synthetic infinite-failure fixtures |
| Closed-loop execution against Phase 2/3 tools | **Yes** — against `computer_control.testing`/`vision.testing` fakes, exactly like Phase 2/3's own integration tests |
| Cancellation | **Yes** — cooperative `asyncio` cancellation, same discipline as `computer_control.core.waiting` |
| `LLMProvider` real model behavior | **No** — no real provider ships in this phase, see §4 |

## 4. `LLMProvider`: abstraction only, no real model (brief §31-34)

Mirrors the exact precedent Phase 3 set with `VisionProvider`/
`NotConfiguredVisionProvider`. `app/services/agent/llm_provider.py`
defines `LLMProvider` (a `Protocol`: `understand`, `plan`, `reason`,
`summarize`, `classify`) and ships exactly one implementation,
`NotConfiguredLLMProvider`, which always returns a structured
"not configured" result — never raises, never calls a network API.

Unlike Phase 3 (where OCR was the "real, no-model-needed" capability
alongside the stub vision provider), Phase 4's equivalent real capability
is a **deterministic, rule-based `IntentInterpreter`/`TaskPlanner`** that
handles a bounded set of goal templates (open an application, search
files, open a file, delete files) via pattern matching — genuinely
functional today, without any LLM, directly satisfying brief §32 ("basic
tasks should eventually work without internet... if no model is
configured, fail gracefully, do not crash"). `ModelRouter`
(`app/services/agent/model_router.py`) is the seam a future phase widens:
in Phase 4 it always routes to the deterministic path, since
`NotConfiguredLLMProvider` is the only provider — the abstraction exists,
the routing complexity does not (brief §34: "do not implement aggressive
routing complexity yet").

## 5. State machine adaptation, precisely

`PLANNING` → `WAITING_PERMISSION` (brief's `VALIDATING`→
`AWAITING_CONFIRMATION`) already exists. `TaskPlanner.create_plan`
performs schema validation, tool-existence validation
(`ToolSelector`), and risk classification *before* returning an
`ExecutionPlan` — an invalid plan never reaches a persisted state at all
(`ErrorCategory.INVALID_PLAN` is raised/returned instead), so a separate
`VALIDATING` database state would record a transition that can never
actually fail once entered, adding a state with no observable failure
edge. `TaskState.TIMED_OUT` is added as newly reachable from `EXECUTING`,
`OBSERVING`, `VERIFYING`, and `RECOVERING` (wherever a budget check can
fire), terminal, distinct from `FAILED` so a caller can tell "ran out of
time/steps" apart from "a tool call failed" without parsing free text.

## 6. Execution reuses `execute_tool_call` directly — no second policy path

A `PlanStep`'s execution *is* a `ToolCallRequest` submitted to the exact
function every other tool call in this codebase goes through
(`app/services/tool_execution.execute_tool_call`). This means:

- Policy evaluation, `PermissionGrant` matching, and the
  CRITICAL-never-pre-authorized rule are inherited automatically — the
  orchestrator contains no risk/permission logic of its own.
- Confirmation is inherited automatically: if `execute_tool_call` returns
  `PERMISSION_DENIED` with `user_action_required=True`, the task
  transitions to `WAITING_PERMISSION` and stops; `ConfirmationManager`
  only builds the human-readable prompt text
  (`docs/security/08-SENSITIVE-ACTION-POLICY.md` §3's "present verbatim
  the exact tool/action, target, risk tier, reason").
- Audit logging is inherited automatically — every step still writes
  exactly one `AuditLog` row, unmodified from Phase 1's contract.
- Resuming after confirmation is simply retrying the identical step
  through `execute_tool_call` again, now that a matching `PermissionGrant`
  exists (created via the existing `POST /permissions`, or a new
  `POST /tasks/{id}/confirm` convenience wrapper around it).

This is the same "one execution path, no bypass" reasoning Phase 2 §3 and
Phase 3 §6 already applied, carried to its logical conclusion: an AI
planner's actions and a human's direct tool invocations are
indistinguishable to the Policy Engine, by construction.

## 7. Verification reuses Phase 3's perception, not a new mechanism

`AgentOrchestrator`'s `OBSERVING`/`VERIFYING` steps call Phase 3 tools
(`screen.observe`, `target.ground`, `scene.diff`, `window.get_active`,
`filesystem.get_metadata`, ...) through the same `execute_tool_call` path
— never a direct import of `vision`/`computer_control`. Brief §46
("never trust the tool call itself as proof of success") is enforced by
policy, not convention: a step's `ActionResult.status` is a necessary but
never sufficient condition for `VERIFYING`→`COMPLETED`; the orchestrator
always issues at least one observation tool call per step with an
`expected_outcome`, and compares the observation against it before
advancing. This is a direct, structural implementation of brief §78/§79's
"the AI's claim must never override real system state" — the orchestrator
never asks an `LLMProvider` whether a step succeeded; the tool
result/observation decides.

## 8. Deterministic planner scope (documented explicitly)

Phase 4 ships real, working plans for a small, explicit set of goal
templates — this is not the "final AI planner" and is not meant to be:

- `open_application` — resolves an app name/alias via the existing
  `ApplicationRegistry` (Phase 2), plans `application.launch` +
  `window.get_active` (verify).
- `search_files` — plans `filesystem.search` (SAFE, no confirmation).
- `open_file` — plans `filesystem.search` (if the target isn't a full
  path) → ambiguity check via `resolve_ambiguity` → `filesystem.open`.
- `delete_files` — plans `filesystem.search` → CRITICAL-risk preview
  (brief §49) → **no delete tool exists** (Phase 2 deliberately never
  built `filesystem.delete` — see `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md`
  §7) → the planner returns `CAPABILITY_UNAVAILABLE`, honestly, rather
  than fabricating a plan for a tool that doesn't exist. This is a direct,
  real instance of brief §69/§70's "if a capability doesn't exist, return
  `CAPABILITY_UNAVAILABLE`, never pretend."
- Any other request → `IntentInterpreter` reports `ambiguity:
  MISSING_INFORMATION` or, for a request naming a capability with no
  tool at all (send a message, control IoT, browse the web), the planner
  returns `CAPABILITY_UNAVAILABLE` immediately, before ever reaching
  `WAITING_PERMISSION` — never scans a network, never discovers a device,
  per brief §71/§72.

## 9. Database: additive extension, not new tables

`Task` gains: `parent_task_id`, `normalized_goal` (JSON), `priority`,
`started_at`/`completed_at`, `current_step`/`total_steps`, `risk_level`,
`requires_confirmation`, `failure_reason`, `result` (JSON),
`extra_metadata` (JSON — not `metadata`, a reserved SQLAlchemy
declarative attribute name). `TaskStep` gains: `description`, `intent`
(JSON), `arguments` (JSON), `expected_outcome`, `actual_result` (JSON),
`confidence`, `started_at`/`completed_at`, `retry_count`, `error` (JSON),
`observation_before`/`observation_after` (JSON — a *reference/summary*,
never a raw screenshot, continuing Phase 3's own discipline of never
persisting pixels). One Alembic migration, same pattern as Phase 2's
`63d3d077887d` (extend) migration. No `task_events`/`task_plans`/
`task_confirmations`/`task_metrics` tables: task events already have a
home (`AuditLog` + the existing `EventBus`/`EventType`, extended
additively with the brief's `task.*` event names); a plan is a
computed-then-executed structure, not something with its own query
pattern yet — same "don't design a schema against a consumer that
doesn't exist" reasoning as Phase 3 §7.

## 10. Simulation mode reuses Phase 2/3's fakes

Brief §91 asks for `FakeBrowser`/`FakeFileSystem`/`FakeWindowManager`/
`FakeScreen`. `computer_control.testing` already ships
`FakeApplicationBackend`/`FakeWindowBackend`/`FakeUIAutomationBackend`/
`FakeScreenBackend`; `vision.testing` already ships `FakeVisionProvider`.
Phase 4's simulation mode (`app/services/agent/simulation.py`) registers
the Tool Registry against these exact fakes (the same `bundle=`/
`vision_provider=` override pattern `register_computer_control_tools`/
`register_vision_tools` already support) rather than reinventing
fake backends. Only `FakeBrowser` is genuinely new, since no browser
tools are registered by any phase yet — it exists as an interface-only
stub matching Phase 3's `BrowserScene`/`BrowserElement` prep work, not a
working fake of a real tool.

## 11. Documentation set for this phase

`docs/phase-4/{AGENT-ARCHITECTURE,TASK-ENGINE,TASK-STATE-MACHINE,INTENT,
PLANNER,TOOL-SELECTION,POLICY-INTEGRATION,CONFIRMATION,RECOVERY,
MODEL-ABSTRACTION,MODEL-ROUTING,CONTEXT-MANAGEMENT,PROMPT-INJECTION,
TRUST-MODEL,HUMAN-IN-THE-LOOP,TASK-MEMORY,AUDIT,PERFORMANCE,
SECURITY-TESTS,PHASE-4-TEST-RESULTS}.md`, each stating plainly what was
verified for real in this environment (nearly everything — this phase is
pure orchestration logic plus calls into already-verified Phase 2/3
tools) versus what remains a deliberate, documented scope boundary (no
real LLM, no browser subsystem, no IoT, no voice/avatar).
