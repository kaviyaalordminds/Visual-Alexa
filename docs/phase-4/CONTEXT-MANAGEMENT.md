# Context Management

`TaskContext`/`ContextManager` (`app/services/agent/context.py`) — brief
§41-42.

## 1. `TaskContext`

A plain dataclass, one instance per `AgentOrchestrator.run` call (never
persisted as its own table — see `TASK-MEMORY.md`): `task_id`,
`user_goal`, `entities`, `constraints`, `current_observation`, `history`
(`StepRecord` list), `errors`, `recovery_state`, `retry_count`,
`replan_count`.

## 2. Bounded summarization (brief §42)

`ContextManager.summarize_for_planning(context)` returns only the most
recent 5 steps and 5 unresolved errors, plus the retry/replan counters —
never the full history. Since no real `LLMProvider` exists yet to size a
prompt for (see `MODEL-ABSTRACTION.md`), "summarization" here means
*bounding* — keeping the decision-relevant tail — rather than natural-
language compression, which would itself require a model. When a real
provider is added, this is the seam that would be extended to actually
condense older entries into prose, without changing its call signature.

## 3. What's preserved

Decisions (which step ran, what tool, what status), unresolved errors,
and the retry/replan counters that gate `RecoveryManager` — exactly the
brief's own list ("important state, decisions, tool results, unresolved
ambiguity, security constraints"), minus "security constraints" which
live in the Policy Engine's own grant/risk data, not duplicated into
`TaskContext`.

## 4. Verified

`tests/unit/test_agent_context.py` (3 tests) — bounding, error
preservation, counter preservation, all pure Python.
