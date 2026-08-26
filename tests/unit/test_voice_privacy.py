"""docs/phase-5/VOICE-PRIVACY.md, brief §50-57 — redact_secrets must never
leak the raw secret value into whatever it's applied to."""

from __future__ import annotations

from voice.core.privacy import redact_secrets


def test_password_value_is_redacted():
    result = redact_secrets("my password is hunter2")
    assert "hunter2" not in result
    assert "[REDACTED]" in result


def test_otp_value_is_redacted():
    result = redact_secrets("the otp is 493021")
    assert "493021" not in result
    assert "[REDACTED]" in result


def test_credit_card_number_is_redacted():
    result = redact_secrets("card number 4111 1111 1111 1111 please")
    assert "4111" not in result
    assert "[REDACTED]" in result


def test_api_key_prefix_is_redacted():
    result = redact_secrets("use sk-abc123XYZ789secret to call the API")
    assert "abc123XYZ789secret" not in result
    assert "[REDACTED]" in result


def test_ordinary_command_is_untouched():
    text = "open chrome and search for cats"
    assert redact_secrets(text) == text


def test_short_numbers_are_not_redacted():
    text = "set a timer for 5 minutes"
    assert redact_secrets(text) == text
