"""TaskStateMachine — a thin, mandatory guard in front of every task state
mutation. docs/phase-4/TASK-STATE-MACHINE.md.

Wraps `veyra_contracts.tasks.is_legal_transition` (Phase 1, already real
and unit-tested) rather than re-implementing transition rules —
docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §1/§5. `AgentOrchestrator`
never sets `Task.state` directly; every mutation goes through
`TaskStateMachine.transition`, so 'never allow arbitrary state
transitions' (brief §8) is structural, not a convention.
"""

from __future__ import annotations

from veyra_contracts import TaskState, is_legal_transition

from app.models.task import Task as TaskRow


class IllegalTaskTransitionError(ValueError):
    def __init__(self, from_state: TaskState, to_state: TaskState) -> None:
        super().__init__(f"Illegal task transition: {from_state.value} -> {to_state.value}")
        self.from_state = from_state
        self.to_state = to_state


class TaskStateMachine:
    def __init__(self, task: TaskRow) -> None:
        self._task = task

    @property
    def state(self) -> TaskState:
        return self._task.state

    def can_transition(self, to_state: TaskState) -> bool:
        return is_legal_transition(self._task.state, to_state)

    def transition(self, to_state: TaskState) -> TaskState:
        if not self.can_transition(to_state):
            raise IllegalTaskTransitionError(self._task.state, to_state)
        from_state = self._task.state
        self._task.state = to_state
        return from_state
