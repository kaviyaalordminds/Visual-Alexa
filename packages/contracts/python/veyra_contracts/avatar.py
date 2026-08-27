"""docs/phase-6/AVATAR-ARCHITECTURE.md — the `TaskState` -> `AgentState`
mapping `docs/phase-4/AGENT-ARCHITECTURE.md` §5 already promised as "a
semantic vocabulary a future UI/avatar can map `TaskState` onto," but
never actually implemented (Phase 4's own words: "No animation, no avatar
rendering — the enum and the mapping convention are the only Phase 4
deliverable here"). This is the real, tested function.

`AgentState.SPEAKING` deliberately has no entry here — it has no
`TaskState` equivalent (VEYRA can be speaking a response about a task
that has already reached a terminal state), so callers set it directly
rather than deriving it from a task.
"""

from __future__ import annotations

from .enums import AgentState, TaskState

_TASK_STATE_TO_AGENT_STATE: dict[TaskState, AgentState] = {
    TaskState.RECEIVED: AgentState.THINKING,
    TaskState.UNDERSTANDING: AgentState.UNDERSTANDING,
    TaskState.PLANNING: AgentState.PLANNING,
    TaskState.WAITING_PERMISSION: AgentState.CONFIRMING,
    TaskState.EXECUTING: AgentState.EXECUTING,
    TaskState.OBSERVING: AgentState.EXECUTING,
    TaskState.VERIFYING: AgentState.EXECUTING,
    TaskState.RECOVERING: AgentState.RECOVERING,
    TaskState.WAITING_USER: AgentState.WAITING,
    TaskState.PAUSED: AgentState.PAUSED,
    TaskState.COMPLETED: AgentState.SUCCESS,
    TaskState.FAILED: AgentState.ERROR,
    TaskState.TIMED_OUT: AgentState.ERROR,
    TaskState.CANCELLED: AgentState.IDLE,
}


def compute_agent_state_from_task(state: TaskState) -> AgentState:
    """Total over every `TaskState` member — a `KeyError` here means a new
    `TaskState` was added without updating this mapping, which is exactly
    the failure mode `test_avatar_mapping.py::test_every_task_state_has_a_mapping`
    exists to catch immediately."""
    return _TASK_STATE_TO_AGENT_STATE[state]
