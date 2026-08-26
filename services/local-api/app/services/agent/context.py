"""TaskContext + ContextManager. docs/phase-4/CONTEXT-MANAGEMENT.md,
docs/phase-4/TASK-MEMORY.md.

Short-term task memory only (brief §40/§83) — everything here lives in
memory for the duration of one `AgentOrchestrator.run` call and is
persisted (as `TaskStep` rows + `Task.result`/`extra_metadata`), never as
a second, parallel long-term memory store. `docs/architecture/09-MEMORY.md`'s
`MemoryCategory`/`MemoryRecord` (Phase 1) is where long-term personal
memory belongs in a future phase — this module never writes to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# docs/phase-4 §42 — do not send the entire task history to a model every
# time. Kept small and explicit rather than a token-counting heuristic,
# since no real LLMProvider exists yet to size a prompt for.
_MAX_RECENT_STEPS = 5


@dataclass
class StepRecord:
    sequence: int
    tool_id: str
    status: str
    summary: str
    error_code: str | None = None


@dataclass
class TaskContext:
    """docs/phase-4 §41."""

    task_id: str
    user_goal: str
    entities: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    current_observation: dict[str, Any] | None = None
    history: list[StepRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recovery_state: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    replan_count: int = 0

    def record_step(self, record: StepRecord) -> None:
        self.history.append(record)

    def record_error(self, message: str) -> None:
        self.errors.append(message)


class ContextManager:
    """docs/phase-4 §42 — summarizes older context while preserving
    decisions, tool results, unresolved ambiguity, and security
    constraints. Pure Python, no model dependency: summarization here
    means bounding history length and keeping the most decision-relevant
    fields, not natural-language compression (that would require a
    configured LLMProvider, which Phase 4 does not ship)."""

    def summarize_for_planning(self, context: TaskContext) -> dict[str, Any]:
        recent = context.history[-_MAX_RECENT_STEPS:]
        return {
            "task_id": context.task_id,
            "goal": context.user_goal,
            "entities": context.entities,
            "constraints": context.constraints,
            "recent_steps": [
                {"sequence": r.sequence, "tool_id": r.tool_id, "status": r.status}
                for r in recent
            ],
            "unresolved_errors": list(context.errors[-_MAX_RECENT_STEPS:]),
            "retry_count": context.retry_count,
            "replan_count": context.replan_count,
        }
