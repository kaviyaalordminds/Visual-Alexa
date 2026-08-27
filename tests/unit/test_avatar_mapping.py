"""docs/phase-6/AVATAR-ARCHITECTURE.md — the TaskState -> AgentState
mapping docs/phase-4/AGENT-ARCHITECTURE.md §5 documented as a convention
but never implemented until Phase 6."""

from __future__ import annotations

import pytest
from veyra_contracts import AgentState, TaskState, compute_agent_state_from_task


def test_every_task_state_has_a_mapping():
    for state in TaskState:
        assert isinstance(compute_agent_state_from_task(state), AgentState)


@pytest.mark.parametrize(
    "task_state, expected",
    [
        (TaskState.RECEIVED, AgentState.THINKING),
        (TaskState.UNDERSTANDING, AgentState.UNDERSTANDING),
        (TaskState.PLANNING, AgentState.PLANNING),
        (TaskState.WAITING_PERMISSION, AgentState.CONFIRMING),
        (TaskState.EXECUTING, AgentState.EXECUTING),
        (TaskState.OBSERVING, AgentState.EXECUTING),
        (TaskState.VERIFYING, AgentState.EXECUTING),
        (TaskState.RECOVERING, AgentState.RECOVERING),
        (TaskState.WAITING_USER, AgentState.WAITING),
        (TaskState.PAUSED, AgentState.PAUSED),
        (TaskState.COMPLETED, AgentState.SUCCESS),
        (TaskState.FAILED, AgentState.ERROR),
        (TaskState.TIMED_OUT, AgentState.ERROR),
        (TaskState.CANCELLED, AgentState.IDLE),
    ],
)
def test_specific_mappings(task_state, expected):
    assert compute_agent_state_from_task(task_state) == expected


def test_speaking_has_no_task_state_equivalent():
    """AgentState.SPEAKING is set directly by the voice layer (VEYRA can
    be speaking a response about an already-terminal task) — no
    TaskState maps to it."""
    assert AgentState.SPEAKING not in {
        compute_agent_state_from_task(state) for state in TaskState
    }
