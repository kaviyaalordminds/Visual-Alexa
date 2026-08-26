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


def test_unrelated_speech_is_unclear_not_guessed():
    result = parse_confirmation("open chrome instead")
    assert result.decision == ConfirmationDecision.UNCLEAR


def test_parser_class_matches_pure_function():
    parser = VoiceConfirmationParser()
    assert parser.parse("yes").decision == ConfirmationDecision.AFFIRM
