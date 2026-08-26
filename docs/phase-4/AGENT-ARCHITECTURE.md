# Agent Architecture

## 1. One orchestrator, not a multi-agent fan-out

Per brief §5, `AgentOrchestrator` (`services/local-api/app/services/agent/orchestrator.py`)
is the single coordinator. It calls specialized *modules* (`IntentInterpreter`,
`TaskPlanner`, `ToolSelector`, `RecoveryManager`, `ConfirmationManager`,
`ContextManager`), never other agents — there is no agent-to-agent
messaging anywhere in this codebase.

```
receive_task (create Task row)
      │
      ▼
  understand (IntentInterpreter)
      │
      ▼
     plan (TaskPlanner + ToolSelector)
      │
      ▼
 execute (closed loop: ACT -> OBSERVE -> VERIFY, via execute_tool_call)
      │
      ├─ success → COMPLETED
      ├─ failure → RECOVERING (RecoveryManager) → retry/replan/ask/abort
      ├─ needs confirmation → WAITING_PERMISSION (ConfirmationManager)
      └─ ambiguous/unclear → WAITING_USER
```

## 2. Where it lives

`services/local-api/app/services/agent/` — not a new top-level package.
See `PHASE-4-IMPLEMENTATION-PLAN.md` §2 for why: the orchestrator needs
direct `Task`/`TaskStep` database access, which CLAUDE.md restricts to the
Local API process alone.

## 3. Module map

| Module | Responsibility |
|---|---|
| `intent.py` | `IntentInterpreter` — text → `StructuredIntent` |
| `planner.py` | `TaskPlanner` — `StructuredIntent` → `ExecutionPlan` |
| `tool_selector.py` | `ToolSelector` — rejects hallucinated tools |
| `confirmation.py` | `ConfirmationManager` — builds prompts |
| `recovery.py` | `RecoveryManager` — diagnoses failures |
| `context.py` | `TaskContext`/`ContextManager` — short-term memory |
| `loop_protection.py` | `LoopBudgetTracker` — hard guardrails |
| `state_machine.py` | `TaskStateMachine` — the one place state mutates |
| `llm_provider.py` | `LLMProvider` Protocol + `NotConfiguredLLMProvider` |
| `model_router.py` | `ModelRouter` — deterministic vs. LLM routing |
| `orchestrator.py` | `AgentOrchestrator` — ties everything together |
| `register.py` | Process-wide singleton wiring |

## 4. Event emission

Every transition publishes an `EventType.TASK_*` event via the existing
Phase 1 `event_bus` — no second event system. See `AUDIT.md` for the
overlapping-but-distinct audit trail.

## 5. Avatar-state mapping (brief §86)

`veyra_contracts.enums.AgentState` (`IDLE`, `LISTENING`, `UNDERSTANDING`,
`THINKING`, `PLANNING`, `EXECUTING`, `WAITING`, `CONFIRMING`,
`RECOVERING`, `SUCCESS`, `ERROR`) exists as a semantic vocabulary a future
UI/avatar can map `TaskState` onto (`WAITING_PERMISSION`→`CONFIRMING`,
`WAITING_USER`→`WAITING`, `COMPLETED`→`SUCCESS`, `FAILED`/`TIMED_OUT`→`ERROR`,
...). No animation, no avatar rendering — the enum and the mapping
convention are the only Phase 4 deliverable here.
