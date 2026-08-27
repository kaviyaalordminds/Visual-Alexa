"""docs/phase-5 §112, brief acceptance test #8 — "Open Rome" with
borderline STT confidence should produce "Did you say Chrome?" instead of
either guessing or failing silently. Never suggests a name that isn't in
the caller-supplied candidate list."""

from __future__ import annotations

from voice.core.mishear import extract_action_target, find_closest_match, suggest_correction

_KNOWN = ["Chrome", "Notepad", "Calculator", "Spotify"]


def test_extracts_verb_and_target():
    assert extract_action_target("open Rome") == ("open", "Rome")
    assert extract_action_target("close Notepad.") == ("close", "Notepad")


def test_does_not_extract_from_unrelated_shapes():
    assert extract_action_target("search for invoice") is None
    assert extract_action_target("") is None


def test_finds_closest_match_above_threshold():
    assert find_closest_match("Rome", _KNOWN) == "Chrome"


def test_no_match_when_nothing_close_enough():
    assert find_closest_match("xyzxyz", _KNOWN) is None


def test_exact_match_is_never_a_suggestion():
    assert find_closest_match("Chrome", _KNOWN) is None


def test_low_confidence_mishear_suggests_correction():
    result = suggest_correction("open Rome", _KNOWN, confidence=0.5)
    assert result is not None
    assert result.suggested_target == "Chrome"
    assert result.corrected_text == "open Chrome"


def test_high_confidence_is_trusted_no_suggestion():
    assert suggest_correction("open Rome", _KNOWN, confidence=0.95) is None


def test_exact_target_never_suggests_even_at_low_confidence():
    assert suggest_correction("open Chrome", _KNOWN, confidence=0.5) is None


def test_non_matching_verb_shape_never_suggests():
    assert suggest_correction("search for invoice", _KNOWN, confidence=0.3) is None


def test_never_fabricates_a_name_outside_the_candidate_list():
    result = suggest_correction("open Zzyzx", _KNOWN, confidence=0.3)
    assert result is None
