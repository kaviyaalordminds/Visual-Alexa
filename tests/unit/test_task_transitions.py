"""docs/architecture/14-TASK-LIFECYCLE.md — legal/illegal transition table."""

from itertools import pairwise

from veyra_contracts import (
    TaskBudget,
    TaskState,
    illegal_task_transition,
    is_legal_transition,
)


def test_happy_path_is_legal():
    path = [
        TaskState.RECEIVED,
        TaskState.UNDERSTANDING,
        TaskState.PLANNING,
        TaskState.WAITING_PERMISSION,
        TaskState.EXECUTING,
        TaskState.OBSERVING,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
    ]
    for a, b in pairwise(path):
        assert is_legal_transition(a, b), f"{a} -> {b} should be legal"


def test_cannot_skip_permission_check():
    assert illegal_task_transition(TaskState.PLANNING, TaskState.EXECUTING)


def test_cannot_skip_verification():
    assert illegal_task_transition(TaskState.EXECUTING, TaskState.COMPLETED)


def test_recovering_can_replan_ask_or_fail():
    assert is_legal_transition(TaskState.RECOVERING, TaskState.PLANNING)
    assert is_legal_transition(TaskState.RECOVERING, TaskState.WAITING_USER)
    assert is_legal_transition(TaskState.RECOVERING, TaskState.FAILED)


def test_cancellation_reachable_from_any_nonterminal_state():
    for state in TaskState:
        if state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            continue
        assert is_legal_transition(state, TaskState.CANCELLED)


def test_terminal_states_have_no_outgoing_transitions():
    for terminal in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
        for state in TaskState:
            assert illegal_task_transition(terminal, state)


def test_task_budget_rejects_unbounded_values():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TaskBudget(max_steps=0, timeout_seconds=30, max_recovery_attempts=1)
    with pytest.raises(ValidationError):
        TaskBudget(max_steps=10, timeout_seconds=100_000, max_recovery_attempts=1)
