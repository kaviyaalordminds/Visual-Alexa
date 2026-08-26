"""docs/phase-3/PRIVACY.md, docs/phase-3/REDACTION.md — Fourth Acceptance
Test's core logic: password fields must classify SECRET and redact."""

from __future__ import annotations

from computer_control.core.models import UIElementInfo
from vision.core.privacy import PrivacyLevel, PrivacyRedactor, SecretDetector, max_privacy_level


def test_password_field_detected_via_uia_flag():
    detector = SecretDetector()
    field = UIElementInfo(automation_id="pwd1", name="", control_type="Edit", is_password=True)
    assert detector.is_password_element(field) is True
    assert detector.classify_element(field) == PrivacyLevel.SECRET


def test_password_field_detected_via_name_fallback():
    detector = SecretDetector()
    field = UIElementInfo(automation_id="txt1", name="Password", control_type="Edit")
    assert detector.is_password_element(field) is True


def test_normal_field_not_classified_secret():
    detector = SecretDetector()
    field = UIElementInfo(automation_id="txt2", name="Username", control_type="Edit")
    assert detector.classify_element(field) == PrivacyLevel.NORMAL


def test_otp_text_detected():
    detector = SecretDetector()
    assert detector.contains_otp("Your one-time code is 482913") is True
    assert detector.contains_otp("Welcome back") is False


def test_credit_card_text_detected():
    detector = SecretDetector()
    assert detector.contains_credit_card("4111 1111 1111 1111") is True
    assert detector.contains_credit_card("call 12345") is False


def test_redactor_redacts_secret_text_never_leaks_raw_value():
    redactor = PrivacyRedactor()
    redacted = redactor.redact_text("482913", PrivacyLevel.SECRET)
    assert redacted == "[REDACTED]"
    assert "482913" not in redacted


def test_redactor_leaves_normal_text_untouched():
    redactor = PrivacyRedactor()
    assert redactor.redact_text("Download", PrivacyLevel.NORMAL) == "Download"


def test_redactor_field_name_redaction_matches_audit_vocabulary():
    redactor = PrivacyRedactor()
    payload = redactor.redact_payload({"password": "hunter2", "path": "/tmp/x"})
    assert payload["password"] == "[REDACTED]"
    assert payload["path"] == "/tmp/x"


def test_max_privacy_level_is_most_sensitive_not_average():
    levels = [PrivacyLevel.PUBLIC, PrivacyLevel.NORMAL, PrivacyLevel.SECRET, PrivacyLevel.NORMAL]
    assert max_privacy_level(levels) == PrivacyLevel.SECRET


def test_max_privacy_level_empty_defaults_normal():
    assert max_privacy_level([]) == PrivacyLevel.NORMAL
