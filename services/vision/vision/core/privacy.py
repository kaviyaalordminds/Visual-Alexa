"""Screen privacy classification, secret detection, and redaction.
docs/phase-3/PRIVACY.md, docs/phase-3/REDACTION.md.

Pure Python, no OS dependency — genuinely tested in this environment (see
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §2).

CLAUDE.md: 'Never hard-code secrets' and docs/security/05-DATA-PROTECTION.md
extend naturally to screen *observations*: a password field's bounds and
existence may be observed, but its *content* must never appear in a log,
an audit row, or (in a future phase) a cloud vision request.
"""

from __future__ import annotations

import re
from enum import StrEnum

from computer_control.core.models import UIElementInfo

# Reuses the exact same field-name vocabulary as
# app/services/audit.py's _SENSITIVE_KEYS (docs/security/06-AUDIT-LOGGING.md
# §5) as its baseline, per docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §1 —
# one redaction vocabulary, not two.
SENSITIVE_FIELD_NAMES = frozenset({"password", "secret", "token", "otp", "credential"})

_PASSWORD_MARKERS = ("password", "passwd", "secret", "pwd")
_OTP_MARKERS = ("otp", "one-time", "verification code", "auth code", "security code")

# docs/phase-3 §29 — "at minimum via UIA password-field metadata where
# available"; these regexes are a *secondary*, best-effort signal over
# observed OCR/UI text, never the sole basis for treating a UIA-flagged
# password field as anything other than SECRET.
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_OTP_CODE_RE = re.compile(r"\b\d{4,8}\b")


class PrivacyLevel(StrEnum):
    """docs/phase-3/PRIVACY.md §1 — ordered least to most sensitive."""

    PUBLIC = "PUBLIC"
    NORMAL = "NORMAL"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    SECRET = "SECRET"


_LEVEL_ORDER: dict[PrivacyLevel, int] = {level: i for i, level in enumerate(PrivacyLevel)}


def max_privacy_level(levels: list[PrivacyLevel]) -> PrivacyLevel:
    """A scene/observation's privacy level is the most sensitive level of
    anything it contains — never the average, never the first."""
    if not levels:
        return PrivacyLevel.NORMAL
    return max(levels, key=lambda level: _LEVEL_ORDER[level])


class SecretDetector:
    """Detects password/OTP/credit-card/token fields. docs/phase-3 §29:
    'at minimum via UIA password-field metadata where available' — that is
    the authoritative signal (`is_password` on `UIElementInfo`/
    `UIElementNode`, set from real UIA state on Windows); text-pattern
    matches are a secondary, best-effort signal over OCR/UI text only.
    """

    def is_password_element(self, element: UIElementInfo) -> bool:
        # `UIElementNode.is_password` (Windows-only, real UIA signal) is
        # checked by callers that have a node; this fallback keeps the
        # detector usable against plain UIElementInfo too, e.g. from a
        # fake backend in a test.
        if getattr(element, "is_password", False):
            return True
        haystack = " ".join(
            filter(None, [element.automation_id, element.name, element.class_name])
        ).lower()
        return any(marker in haystack for marker in _PASSWORD_MARKERS)

    def contains_otp(self, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in _OTP_MARKERS) and bool(
            _OTP_CODE_RE.search(text)
        )

    def contains_credit_card(self, text: str) -> bool:
        digits_only = re.sub(r"[ -]", "", text)
        return bool(_CREDIT_CARD_RE.search(text)) and 13 <= len(digits_only) <= 19

    def classify_element(self, element: UIElementInfo) -> PrivacyLevel:
        if self.is_password_element(element):
            return PrivacyLevel.SECRET
        return PrivacyLevel.NORMAL

    def classify_text(self, text: str) -> PrivacyLevel:
        if self.contains_otp(text) or self.contains_credit_card(text):
            return PrivacyLevel.SECRET
        return PrivacyLevel.NORMAL


class PrivacyRedactor:
    """docs/phase-3/REDACTION.md — redacts by UI-element privacy
    classification (a password *field*, not just a JSON key named
    "password"), extending (not replacing) the existing field-name
    redaction in app/services/audit.py."""

    def __init__(self, detector: SecretDetector | None = None) -> None:
        self._detector = detector or SecretDetector()

    def redact_text(self, text: str, level: PrivacyLevel) -> str:
        if level in (PrivacyLevel.SECRET, PrivacyLevel.SENSITIVE):
            return "[REDACTED]"
        return text

    def redact_element_text(self, element: UIElementInfo, text: str | None) -> str | None:
        if text is None:
            return None
        level = self._detector.classify_element(element)
        return self.redact_text(text, level)

    def redact_field_name(self, key: str, value: object) -> object:
        return "[REDACTED]" if key.lower() in SENSITIVE_FIELD_NAMES else value

    def redact_payload(self, payload: dict[str, object]) -> dict[str, object]:
        return {key: self.redact_field_name(key, value) for key, value in payload.items()}
