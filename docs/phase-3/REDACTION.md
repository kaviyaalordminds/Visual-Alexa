# Redaction

`vision.core.privacy.PrivacyRedactor` extends, rather than replaces,
`app/services/audit.py`'s existing `_SENSITIVE_KEYS` field-name redaction
(`password`, `secret`, `token`, `otp`, `credential` — re-exported as
`vision.core.privacy.SENSITIVE_FIELD_NAMES`, the exact same set).

## 1. Two redaction axes

- **By field name** (`redact_payload`/`redact_field_name`) — the existing
  audit-log convention: a JSON key named `password` is always redacted
  regardless of its value's shape.
- **By UI-element privacy classification** (`redact_text`/
  `redact_element_text`) — new in Phase 3: a password *field*'s observed
  text is redacted based on what the field *is* (a password box), not
  merely what its containing key is named. `ObservationCoordinator.observe`
  applies this to every OCR `TextRegion` before it is returned, so an OTP
  code or credit-card number recognized by OCR is replaced with
  `"[REDACTED]"` in the `ScreenObservation` — never round-tripped as
  plaintext into the tool result or the `AuditLog` row it feeds.

## 2. Never logged

Since every Phase 3 tool result flows through the existing
`write_audit_log` (`app/services/audit.py`), and `ScreenObservation`'s
`text_regions` are already redacted before being placed in that result,
no additional audit-layer change was needed to keep secrets out of the
audit trail — redaction happens once, at the point of observation, not
re-applied ad hoc at the logging boundary.
