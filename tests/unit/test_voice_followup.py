"""docs/phase-5 §28-31 — resolve_followup rewrites ordinal/pronoun
follow-ups into concrete text; it must never fabricate a target when
nothing in the session supports one."""

from __future__ import annotations

from veyra_contracts import AmbiguityCandidate
from voice.core.followup import resolve_followup
from voice.core.models import VoiceSession


def _session_with_candidates() -> VoiceSession:
    return VoiceSession(
        last_candidates=[
            AmbiguityCandidate(id="1", label="project1.txt"),
            AmbiguityCandidate(id="2", label="project2.txt"),
        ]
    )


def test_ordinal_second_one_resolves_to_second_candidate():
    session = _session_with_candidates()
    result = resolve_followup("open the second one", session)
    assert result == "open the project2.txt"


def test_ordinal_first_one_resolves_to_first_candidate():
    session = _session_with_candidates()
    result = resolve_followup("open the first one", session)
    assert result == "open the project1.txt"


def test_number_option_resolves_by_index():
    session = _session_with_candidates()
    result = resolve_followup("open number 1", session)
    assert result == "open project1.txt"


def test_pronoun_resolves_against_single_remaining_candidate():
    session = VoiceSession(last_candidates=[AmbiguityCandidate(id="1", label="report.docx")])
    result = resolve_followup("open it", session)
    assert result == "open report.docx"


def test_pronoun_resolves_against_last_task_goal_when_no_candidates():
    session = VoiceSession(last_task_goal="Spotify")
    result = resolve_followup("open it", session)
    assert result == "open Spotify"


def test_ordinary_command_with_no_context_returns_none():
    session = VoiceSession()
    assert resolve_followup("open Chrome", session) is None


def test_ordinal_out_of_range_returns_none():
    session = _session_with_candidates()
    assert resolve_followup("open the fifth one", session) is None


def test_pronoun_with_no_candidates_and_no_goal_returns_none():
    session = VoiceSession()
    assert resolve_followup("open it", session) is None
