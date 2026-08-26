"""LoopBudgetTracker — hard guardrails against unbounded execution.
docs/phase-4/TASK-ENGINE.md, brief §28/§73. CLAUDE.md: 'no unbounded
loops, ever.'

Every `AgentOrchestrator` run owns exactly one tracker, seeded from the
task's `TaskBudget`. `RecoveryManager` bounds *retries of a single step*;
this module bounds the *whole run* — total steps, elapsed wall time, total
replans, and identical-call loop detection across the entire task.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from veyra_contracts import TaskBudget

# docs/phase-4 §28 — the same (tool_id, arguments) pair appearing this
# many times within the tracked window is treated as a stuck loop, not
# legitimate repeated work.
_LOOP_REPEAT_THRESHOLD = 3
_LOOP_WINDOW = 10


@dataclass
class LoopBudgetTracker:
    budget: TaskBudget
    _started_at: float = field(default_factory=time.monotonic)
    steps_executed: int = 0
    total_retries: int = 0
    total_replans: int = 0
    _recent_calls: list[str] = field(default_factory=list)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_at

    def record_step(self) -> None:
        self.steps_executed += 1

    def record_retry(self) -> None:
        self.total_retries += 1

    def record_replan(self) -> None:
        self.total_replans += 1

    def budget_exceeded_reason(self) -> str | None:
        if self.steps_executed >= self.budget.max_steps:
            return f"max_steps ({self.budget.max_steps}) exceeded."
        if self.elapsed_seconds() >= self.budget.timeout_seconds:
            return f"timeout_seconds ({self.budget.timeout_seconds}) exceeded."
        if self.total_replans > self.budget.max_replans:
            return f"max_replans ({self.budget.max_replans}) exceeded."
        return None

    def record_call_and_check_loop(self, tool_id: str, arguments: dict[str, Any]) -> bool:
        """Records a (tool_id, arguments) call and returns True if this
        exact call has now repeated `_LOOP_REPEAT_THRESHOLD` times within
        the tracked window — a real, structural loop, not merely 'the
        same tool used more than once' (e.g. searching multiple roots
        legitimately calls filesystem.search repeatedly with *different*
        arguments)."""
        key = f"{tool_id}:{json.dumps(arguments, sort_keys=True, default=str)}"
        self._recent_calls.append(key)
        if len(self._recent_calls) > _LOOP_WINDOW:
            self._recent_calls.pop(0)
        return self._recent_calls.count(key) >= _LOOP_REPEAT_THRESHOLD
