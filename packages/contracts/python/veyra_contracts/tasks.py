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
    # Phase 4 (docs/phase-4/TASK-STATE-MACHINE.md): PLANNING -> WAITING_USER
    # is new — ambiguity discovered while *building* a plan (e.g. multiple
    # candidate files) surfaces here, not only during UNDERSTANDING.
    TaskState.PLANNING: frozenset({TaskState.WAITING_PERMISSION, TaskState.WAITING_USER}),
    TaskState.WAITING_PERMISSION: frozenset(
        {TaskState.EXECUTING, TaskState.FAILED, TaskState.TIMED_OUT}
    ),
    # Phase 4: EXECUTING -> WAITING_PERMISSION is new — a later step in a
    # multi-step plan can require fresh confirmation mid-execution, not
    # only once before the first step. EXECUTING -> WAITING_USER is new —
    # human-in-the-loop pause (CAPTCHA/2FA/unexpected prompt, brief
    # §57/§58), distinct from a permission gate. EXECUTING -> RECOVERING
    # is new — matches the brief's own §8 failure diagram ('EXECUTING ->
    # RECOVERING -> RETRY or REPLAN') directly, for a step that fails
    # before any observation was even attempted. EXECUTING -> FAILED is
    # new — a planned call to an unregistered ('hallucinated') tool is
    # rejected immediately (brief §77), never attempted, so there is
    # nothing to diagnose/retry in RECOVERING first.
    # Phase 5 (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md): EXECUTING ->
    # PAUSED is new — a real, cooperative pause (the voice layer's "Wait"
    # interruption, brief §14), distinct from WAITING_PERMISSION/
    # WAITING_USER (neither of which the user asked for mid-execution).
    TaskState.EXECUTING: frozenset(
        {
            TaskState.OBSERVING,
            TaskState.WAITING_PERMISSION,
            TaskState.WAITING_USER,
            TaskState.RECOVERING,
            TaskState.PAUSED,
            TaskState.FAILED,
            TaskState.TIMED_OUT,
        }
    ),
    TaskState.OBSERVING: frozenset({TaskState.VERIFYING, TaskState.TIMED_OUT}),
    TaskState.VERIFYING: frozenset(
        {TaskState.COMPLETED, TaskState.RECOVERING, TaskState.TIMED_OUT}
    ),
    TaskState.RECOVERING: frozenset(
        {
            TaskState.PLANNING,
            TaskState.EXECUTING,
            TaskState.WAITING_USER,
            TaskState.FAILED,
            TaskState.TIMED_OUT,
        }
    ),
    # Phase 4: WAITING_USER -> EXECUTING is new — resuming a
    # human-in-the-loop pause (brief §58: '...USER COMPLETES
    # AUTHENTICATION -> VEYRA RESUMES') continues execution directly,
    # never forces a full replan.
    TaskState.WAITING_USER: frozenset(
        {
            TaskState.UNDERSTANDING,
            TaskState.PLANNING,
            TaskState.EXECUTING,
            TaskState.FAILED,
            TaskState.TIMED_OUT,
        }
    ),
    # Resuming a pause continues the *same* plan, never a full replan —
    # same discipline as WAITING_PERMISSION/WAITING_USER's own resume.
    TaskState.PAUSED: frozenset({TaskState.EXECUTING}),
    # Terminal states: no further transitions.
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
    TaskState.TIMED_OUT: frozenset(),
}

_TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.TIMED_OUT}
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
    CLAUDE.md: 'No unbounded loops, ever.' Phase 4
    (docs/phase-4/TASK-ENGINE.md, brief §28/§73) adds `max_replans`
    additively, with a default so existing callers (Phase 1's `/tasks`
    API, existing tests) that never set it keep working unchanged."""

    max_steps: int = Field(gt=0, le=100)
    timeout_seconds: int = Field(gt=0, le=3600)
    max_recovery_attempts: int = Field(ge=0, le=10)
    max_replans: int = Field(default=3, ge=0, le=10)
