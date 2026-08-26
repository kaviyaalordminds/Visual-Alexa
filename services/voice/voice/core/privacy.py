"""redact_secrets — strips values a transcript must never persist
verbatim. docs/phase-5/VOICE-PRIVACY.md, brief §50-57 and the "secret
logging" security test (brief §102-103).

Applied to whatever text a caller is about to *store* (a `Message` row) —
never to text actually spoken back to the user, which would just be
confusing. This is a conservative pattern-based scrubber, not a general
PII detector — it is intentionally biased toward over-redacting a
plausible secret (e.g. any long digit run) rather than under-redacting a
real one.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # "password is X" / "my PIN: X" -> keep the label, drop the value.
    (re.compile(r"(?i)\b(password|passcode|pin)\s+(?:is|:)\s*\S+"), r"\1 [REDACTED]"),
    # "otp is 123456" / "verification code: 123456"
    (
        re.compile(
            r"(?i)\b(otp|one-time code|one time code|verification code)\s+(?:is|:)\s*\d{4,8}\b"
        ),
        r"\1 [REDACTED]",
    ),
    # Credit-card-shaped digit runs (13-19 digits, optional space/dash
    # separators) — deliberately broad; a false positive just over-redacts.
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED]"),
    # Common API key/token prefixes (OpenAI, GitHub, GitLab, Slack, bearer
    # tokens) followed by their opaque value.
    (re.compile(r"\b(?:sk-|ghp_|gho_|glpat-|xox[baprs]-|Bearer\s+)\S+"), "[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """docs/phase-5 §50-57. Pure function — no I/O, no model call."""
    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
