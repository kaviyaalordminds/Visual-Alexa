"""docs/phase-5/VOICE-SECURITY.md, brief §46-49 — the one hard security
rule: unclear/low-confidence audio must never be treated as authorization."""

from __future__ import annotations

from voice.core.confirmation import VoiceConfirmationParser, parse_confirmation
from voice.core.enums import ConfirmationDecision


def test_yes_is_affirm():
    assert parse_confirmation("yes").decision == ConfirmationDecision.AFFIRM


def test_okay_is_affirm():
    assert parse_confirmation("okay").decision == ConfirmationDecision.AFFIRM


def test_no_is_deny():
    assert parse_confirmation("no").decision == ConfirmationDecision.DENY


def test_continue_and_resume_are_affirm():
    """docs/phase-5/BARGE-IN.md — the reply to a real paused task's
    'Say continue when you're ready.'"""
    assert parse_confirmation("continue").decision == ConfirmationDecision.AFFIRM
    assert parse_confirmation("resume").decision == ConfirmationDecision.AFFIRM


def test_cancel_is_deny():
    assert parse_confirmation("cancel").decision == ConfirmationDecision.DENY


def test_hedged_phrasing_is_unclear_never_affirm():
    """brief §48's exact scenario: 'yeah... maybe' must never authorize."""
    result = parse_confirmation("yeah... maybe")
    assert result.decision == ConfirmationDecision.UNCLEAR
    assert result.decision != ConfirmationDecision.AFFIRM


def test_low_confidence_yes_is_still_unclear():
    """Even an exact phrase match is gated by confidence first — low STT
    confidence must never be treated as authorization just because the
    words happened to match."""
    result = parse_confirmation("yes", confidence=0.4)
    assert result.decision == ConfirmationDecision.UNCLEAR


def test_high_confidence_yes_is_affirm():
    result = parse_confirmation("yes", confidence=0.95)
    assert result.decision == ConfirmationDecision.AFFIRM


def test_empty_text_is_unclear():
    assert parse_confirmation("").decision == ConfirmationDecision.UNCLEAR


def test_denial_embedded_in_a_longer_sentence_is_deny():
    """brief's live-correction scenario: 'Actually, don't open it' must be
    understood as a denial, not left UNCLEAR just because it isn't an
    exact phrase match."""
    result = parse_confirmation("Actually, don't open it")
    assert result.decision == ConfirmationDecision.DENY


def test_embedded_denial_leniency_never_extends_to_affirm():
    """The asymmetry is the point: embedded-phrase matching only ever
    helps DENY. 'yeah... maybe' contains the bare word 'yeah' but must
    still never resolve to AFFIRM."""
    result = parse_confirmation("yeah... maybe")
    assert result.decision != ConfirmationDecision.AFFIRM
    assert result.decision == ConfirmationDecision.UNCLEAR


def test_embedded_denial_still_gated_by_confidence():
    result = parse_confirmation("actually, don't do that", confidence=0.3)
    assert result.decision == ConfirmationDecision.UNCLEAR


def test_unrelated_speech_is_unclear_not_guessed():
    result = parse_confirmation("open chrome instead")
    assert result.decision == ConfirmationDecision.UNCLEAR


def test_parser_class_matches_pure_function():
    parser = VoiceConfirmationParser()
    assert parser.parse("yes").decision == ConfirmationDecision.AFFIRM
