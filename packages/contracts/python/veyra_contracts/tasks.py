"""Task lifecycle contracts. docs/architecture/14-TASK-LIFECYCLE.md"""

from __future__ import annotations

from pydantic import BaseModel, Field

from veyra_contracts.enums import TaskState

# Legal transitions, matching the state diagram in
# docs/architecture/14-TASK-LIFECYCLE.md §1. CANCELLED is reachable from any
# non-terminal state (handled separately in `is_legal_transition`), so it is
# not listed explicitly in every row.
_LEGAL_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.RECEIVED: frozenset({TaskState.UNDERSTANDING}),
    TaskState.UNDERSTANDING: frozenset({TaskState.PLANNING, TaskState.WAITING_USER}),
    TaskState.PLANNING: frozenset({TaskState.WAITING_PERMISSION}),
    TaskState.WAITING_PERMISSION: frozenset({TaskState.EXECUTING, TaskState.FAILED}),
    TaskState.EXECUTING: frozenset({TaskState.OBSERVING}),
    TaskState.OBSERVING: frozenset({TaskState.VERIFYING}),
    TaskState.VERIFYING: frozenset({TaskState.COMPLETED, TaskState.RECOVERING}),
    TaskState.RECOVERING: frozenset(
        {TaskState.PLANNING, TaskState.WAITING_USER, TaskState.FAILED}
    ),
    TaskState.WAITING_USER: frozenset(
        {TaskState.UNDERSTANDING, TaskState.PLANNING, TaskState.FAILED}
    ),
    # Terminal states: no further transitions.
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}

_TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
)


def is_legal_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """CANCELLED is reachable from any non-terminal state (explicit user or
    system cancellation, per docs/architecture/14-TASK-LIFECYCLE.md §1)."""
    if from_state in _TERMINAL_STATES:
        return False
    if to_state == TaskState.CANCELLED:
        return True
    return to_state in _LEGAL_TRANSITIONS.get(from_state, frozenset())


def illegal_task_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """Inverse convenience predicate, used by validators/tests that want to
    assert a transition is rejected."""
    return not is_legal_transition(from_state, to_state)


class TaskBudget(BaseModel):
    """Mandatory guardrails for every autonomous execution loop.
    CLAUDE.md: 'No unbounded loops, ever.'"""

    max_steps: int = Field(gt=0, le=100)
    timeout_seconds: int = Field(gt=0, le=3600)
    max_recovery_attempts: int = Field(ge=0, le=10)
