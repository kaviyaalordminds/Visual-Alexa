"""VoiceStateMachine — deterministic voice session state transitions.
docs/phase-5/VOICE-STATE-MACHINE.md, brief §43.

Mirrors `veyra_contracts.tasks.is_legal_transition`'s exact pattern
(docs/phase-4/TASK-STATE-MACHINE.md) — a real, unit-tested transition
table, not a loose set of status strings a caller could set arbitrarily.
"""

from __future__ import annotations

from voice.core.enums import VoiceState
from voice.core.models import VoiceSession

_LEGAL_TRANSITIONS: dict[VoiceState, frozenset[VoiceState]] = {
    VoiceState.IDLE: frozenset({VoiceState.WAKE_DETECTED, VoiceState.LISTENING}),
    VoiceState.WAKE_DETECTED: frozenset({VoiceState.LISTENING, VoiceState.IDLE}),
    # LISTENING -> IDLE: no speech detected before a silence timeout.
    VoiceState.LISTENING: frozenset({VoiceState.TRANSCRIBING, VoiceState.IDLE}),
    # TRANSCRIBING -> IDLE: an empty/silent transcript, nothing to act on.
    VoiceState.TRANSCRIBING: frozenset({VoiceState.UNDERSTANDING, VoiceState.IDLE}),
    # UNDERSTANDING -> RESPONDING directly: a clarifying question needs no
    # EXECUTING step (brief §96 — 'ask, do not guess').
    VoiceState.UNDERSTANDING: frozenset({VoiceState.EXECUTING, VoiceState.RESPONDING}),
    VoiceState.EXECUTING: frozenset({VoiceState.RESPONDING}),
    VoiceState.RESPONDING: frozenset({VoiceState.IDLE, VoiceState.INTERRUPTED}),
    # INTERRUPTED -> LISTENING: barge-in immediately starts listening to
    # whatever the user says next (brief §13).
    VoiceState.INTERRUPTED: frozenset({VoiceState.LISTENING, VoiceState.IDLE}),
    VoiceState.RECOVERY: frozenset({VoiceState.IDLE, VoiceState.ERROR}),
    # ERROR's only legal exit is RECOVERY (enforced again, explicitly, by
    # the guard at the top of is_legal_transition below) — not terminal.
    VoiceState.ERROR: frozenset({VoiceState.RECOVERY}),
    # Terminal.
    VoiceState.ENDED: frozenset(),
}

# ERROR and ENDED are reachable from any non-terminal state — the same
# 'CANCELLED reachable from anywhere' rule Phase 1/4's TaskState uses.
_TERMINAL_STATES: frozenset[VoiceState] = frozenset({VoiceState.ENDED})
_ALWAYS_REACHABLE: frozenset[VoiceState] = frozenset({VoiceState.ERROR, VoiceState.ENDED})


def is_legal_transition(from_state: VoiceState, to_state: VoiceState) -> bool:
    if from_state == VoiceState.ERROR and to_state != VoiceState.RECOVERY:
        return False
    if from_state in _TERMINAL_STATES:
        return False
    if to_state in _ALWAYS_REACHABLE:
        return True
    return to_state in _LEGAL_TRANSITIONS.get(from_state, frozenset())


class IllegalVoiceTransitionError(ValueError):
    def __init__(self, from_state: VoiceState, to_state: VoiceState) -> None:
        super().__init__(f"Illegal voice state transition: {from_state.value} -> {to_state.value}")
        self.from_state = from_state
        self.to_state = to_state


class VoiceStateMachine:
    """Wraps a `VoiceSession`, the same mandatory-guard pattern
    `TaskStateMachine` uses for `Task.state` — `session.status` is never
    set directly by a caller."""

    def __init__(self, session: VoiceSession) -> None:
        self._session = session

    @property
    def state(self) -> VoiceState:
        return self._session.status

    def can_transition(self, to_state: VoiceState) -> bool:
        return is_legal_transition(self._session.status, to_state)

    def transition(self, to_state: VoiceState) -> VoiceState:
        if not self.can_transition(to_state):
            raise IllegalVoiceTransitionError(self._session.status, to_state)
        from_state = self._session.status
        self._session.status = to_state
        return from_state
