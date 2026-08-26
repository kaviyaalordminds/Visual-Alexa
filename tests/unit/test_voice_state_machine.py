"""docs/phase-5/VOICE-STATE-MACHINE.md, brief §43 — the same
'no caller sets state directly' discipline TaskStateMachine uses."""

from __future__ import annotations

import pytest
from voice.core.enums import VoiceState
from voice.core.models import VoiceSession
from voice.core.state_machine import (
    IllegalVoiceTransitionError,
    VoiceStateMachine,
    is_legal_transition,
)


def test_happy_path_wake_to_responding():
    session = VoiceSession()
    sm = VoiceStateMachine(session)
    for state in (
        VoiceState.WAKE_DETECTED,
        VoiceState.LISTENING,
        VoiceState.TRANSCRIBING,
        VoiceState.UNDERSTANDING,
        VoiceState.EXECUTING,
        VoiceState.RESPONDING,
        VoiceState.IDLE,
    ):
        sm.transition(state)
    assert sm.state == VoiceState.IDLE


def test_understanding_can_skip_executing_for_a_clarifying_question():
    session = VoiceSession(status=VoiceState.UNDERSTANDING)
    sm = VoiceStateMachine(session)
    sm.transition(VoiceState.RESPONDING)
    assert sm.state == VoiceState.RESPONDING


def test_barge_in_interrupted_returns_to_listening():
    session = VoiceSession(status=VoiceState.RESPONDING)
    sm = VoiceStateMachine(session)
    sm.transition(VoiceState.INTERRUPTED)
    sm.transition(VoiceState.LISTENING)
    assert sm.state == VoiceState.LISTENING


def test_illegal_transition_raises_and_never_mutates_state():
    session = VoiceSession(status=VoiceState.IDLE)
    sm = VoiceStateMachine(session)
    with pytest.raises(IllegalVoiceTransitionError):
        sm.transition(VoiceState.EXECUTING)
    assert sm.state == VoiceState.IDLE


def test_error_is_reachable_from_any_non_terminal_state():
    for state in (VoiceState.LISTENING, VoiceState.EXECUTING, VoiceState.RESPONDING):
        assert is_legal_transition(state, VoiceState.ERROR)


def test_errors_only_legal_exit_is_recovery():
    assert is_legal_transition(VoiceState.ERROR, VoiceState.RECOVERY)
    assert not is_legal_transition(VoiceState.ERROR, VoiceState.IDLE)
    assert not is_legal_transition(VoiceState.ERROR, VoiceState.LISTENING)


def test_ended_is_terminal():
    for state in VoiceState:
        assert not is_legal_transition(VoiceState.ENDED, state)


def test_error_has_exactly_one_legal_exit():
    legal_exits = [state for state in VoiceState if is_legal_transition(VoiceState.ERROR, state)]
    assert legal_exits == [VoiceState.RECOVERY]


def test_can_transition_does_not_mutate_state():
    session = VoiceSession(status=VoiceState.IDLE)
    sm = VoiceStateMachine(session)
    assert sm.can_transition(VoiceState.LISTENING) is True
    assert sm.can_transition(VoiceState.EXECUTING) is False
    assert sm.state == VoiceState.IDLE
