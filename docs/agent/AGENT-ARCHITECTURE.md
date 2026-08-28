# Agent Architecture (Phase 11 index)

Phase 11 ("Autonomous Multi-Step Task Execution & Agent Orchestration
Engine") audited the existing repository first, per its own explicit
instruction, and found that almost the entire requested architecture
already existed and was real — built incrementally across Phase 4 (the
task engine itself), Phase 5 (pause/resume, barge-in), Phase 7 (dynamic
tool discovery), Phase 8 (browser tools), Phase 9 (reliability hardening),
and Phase 10 (production hardening). This `docs/agent/` set documents the
architecture as it exists **after** Phase 11, cross-referencing the
detailed Phase 4/5/8 docs it builds on rather than duplicating them.

## What Phase 11 actually added

Three real, bounded, tested capabilities — no rewrite of anything working:

1. **Real `REPLAN` recovery** (`docs/agent/RECOVERY.md`) — replaced an
   always-fails stub with genuine re-planning against refreshed context,
   reusing the exact same planning code path as the first plan.
2. **`WorkflowMemory` alias resolution** (`docs/agent/ORCHESTRATION.md` §4)
   — the planner now consults real `Memory` rows (`category=WORKFLOW`) to
   resolve user-defined aliases like "office folder" before falling back
   to search, per `docs/architecture/09-MEMORY.md` §4's own long-specified
   contract.
3. **A real `browser_task` planning template** (`docs/agent/ORCHESTRATION.md`
   §5) — built on Phase 8's already-real Playwright browser tools;
   deliberately bounded to launch+search+observe, never a guessed
   multi-step click sequence.

Everything else Phase 11's brief described — the Intent Engine, Task
Manager, Planner, Plan Validator (`ToolSelector` + Policy Engine),
Execution Engine, Observation/Verification (the ACT→OBSERVE→VERIFY loop),
Confirmation Manager, Task Memory, Execution Context, Task Event Stream,
Cancellation Manager, retry/loop-budget bounding, and Agent State mapping
— already existed, real and tested, before this phase began. This index
says where each one lives; it does not re-derive them.

## Component map

| Phase 11 term | Real module | Doc |
|---|---|---|
| Intent Engine | `app/services/agent/intent.py` (`IntentInterpreter`) | `docs/phase-4/INTENT.md` |
| Task Manager | `app/api/tasks.py` + `app/models/task.py` | `docs/agent/TASK-LIFECYCLE.md` |
| Planner | `app/services/agent/planner.py` (`TaskPlanner`) | `docs/phase-4/PLANNER.md`, `docs/agent/ORCHESTRATION.md` |
| Plan Validator | `ToolSelector` (rejects hallucinated tools) + Policy Engine (gates every call) | `docs/agent/SECURITY-GATES.md` |
| Tool Registry / Tool Selector | `app/services/tool_registry.py`, `app/services/agent/tool_selector.py` | `docs/agent/TOOL-REGISTRY.md` |
| Execution Engine | `AgentOrchestrator._execute_plan` (`orchestrator.py`) | `docs/agent/ORCHESTRATION.md` |
| Observation / Verification Engine | Per-tool `ToolResult` + step verification (`verification_strategy` on `PlanStep`) | `docs/agent/ORCHESTRATION.md` §3 |
| Recovery Engine | `app/services/agent/recovery.py` (`RecoveryManager`) | `docs/agent/RECOVERY.md` |
| Confirmation Manager | `app/services/agent/confirmation.py` + Policy Engine | `docs/agent/CONFIRMATION.md` |
| Task Memory / Execution Context | `app/services/agent/context.py` (`TaskContext`, short-term, in-run only) | `docs/phase-4/CONTEXT-MANAGEMENT.md` |
| Task Event Stream | `EventBus` + `/events` WebSocket, `EventType.TASK_*` | `docs/agent/EVENT-SYSTEM.md` |
| Cancellation / Pause Manager | `request_cancellation`/`request_pause` (in-memory, process-global) in `orchestrator.py` | `docs/agent/TASK-LIFECYCLE.md` §3 |
| Retry / Loop Budget | `app/services/agent/loop_protection.py` (`LoopBudgetTracker`) | `docs/phase-4/TASK-ENGINE.md` |
| Agent State Manager | `TaskStateMachine` (`state_machine.py`) — the one place `Task.state` mutates | `docs/agent/TASK-LIFECYCLE.md` |
| Result Synthesizer | `Task.result` (JSON, per-outcome-shape) — no separate synthesis module; the orchestrator writes the final shape directly at each terminal state | `docs/agent/ORCHESTRATION.md` |

## One orchestrator, no multi-agent fan-out

Unchanged from Phase 4 (`docs/phase-4/AGENT-ARCHITECTURE.md` §1):
`AgentOrchestrator` is the single coordinator. It calls specialized
modules and the one shared `execute_tool_call` chokepoint — never other
agents. Phase 11 did not introduce agent-to-agent messaging, a second
orchestrator, or a parallel execution path; the brief's own "DO NOT
create a second AI architecture" constraint holds by construction (there
is exactly one `AgentOrchestrator` class and one process-wide singleton,
`app/services/agent/register.py`).

## Security posture (unchanged, re-verified)

Every Phase 11 addition still passes through the same, single, unconditional
chain: `AgentOrchestrator._call_tool` → `execute_tool_call` →
`PolicyEngine.evaluate` → registered executor → `AuditLog`. No new code
path from model output (there is still no LLM in the planning loop — see
`docs/agent/ORCHESTRATION.md` §1) to `exec()`, shell, or unrestricted file
I/O was added. See `docs/agent/SECURITY-GATES.md`.
