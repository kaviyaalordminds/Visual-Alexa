"""docs/phase-5/BARGE-IN.md, brief §11-14 — the six named interruption
phrases plus the "Stop talking" vs. "Stop Chrome" contextual
disambiguation the brief explicitly calls out."""

from __future__ import annotations

from voice.core.enums import InterruptionType
from voice.core.interruption import InterruptionClassifier, classify_interruption


def test_bare_stop_means_stop_speaking():
    result = classify_interruption("Stop.")
    assert result.matched is True
    assert result.interruption_type == InterruptionType.STOP_SPEAKING


def test_stop_talking_means_stop_speaking():
    result = classify_interruption("Stop talking")
    assert result.interruption_type == InterruptionType.STOP_SPEAKING


def test_stop_named_target_means_cancel_task():
    result = classify_interruption("Stop Chrome")
    assert result.interruption_type == InterruptionType.CANCEL_TASK


def test_cancel_means_cancel_task():
    assert classify_interruption("Cancel").interruption_type == InterruptionType.CANCEL_TASK


def test_wait_means_pause_task():
    assert classify_interruption("Wait").interruption_type == InterruptionType.PAUSE_TASK


def test_pause_means_pause_task():
    assert classify_interruption("Pause").interruption_type == InterruptionType.PAUSE_TASK


def test_never_mind_means_cancel_task():
    assert classify_interruption("Never mind").interruption_type == InterruptionType.CANCEL_TASK


def test_thats_enough_means_stop_speaking():
    result = classify_interruption("That's enough")
    assert result.interruption_type == InterruptionType.STOP_SPEAKING


def test_ordinary_command_does_not_match():
    result = classify_interruption("open chrome")
    assert result.matched is False
    assert result.interruption_type is None


def test_empty_text_does_not_match():
    assert classify_interruption("").matched is False


def test_classifier_class_matches_pure_function():
    classifier = InterruptionClassifier()
    assert classifier.classify("Cancel").interruption_type == InterruptionType.CANCEL_TASK
