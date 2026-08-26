# Privacy

## 1. Classification (`vision.core.privacy.PrivacyLevel`)

`PUBLIC < NORMAL < PRIVATE < SENSITIVE < SECRET`, ordered least to most
sensitive. `max_privacy_level(levels)` — the level of an observation is
the **most** sensitive thing it contains, never an average, never the
first.

## 2. Secret detection (`SecretDetector`)

- **Password fields**: `is_password_element` checks the real UIA
  `is_password` signal first (`UIElementNode.is_password`, see
  `UI-TREE.md` §3), falling back to a name/automation-id/class-name
  substring match only when that signal is unavailable. This matches the
  brief's "at minimum via UIA password-field metadata where available."
- **OTP codes**: `contains_otp` requires both an OTP-context keyword
  ("otp", "one-time", "verification code", ...) *and* a 4-8 digit number
  in the same text — a bare 6-digit number alone is not flagged, avoiding
  false positives on ordinary numeric text.
- **Credit card numbers**: `contains_credit_card` matches a 13-19 digit
  span (with optional spaces/dashes), the standard PAN length range.

## 3. Classification points

- `SecretDetector.classify_element(UIElementInfo)` → SECRET for a
  password field, NORMAL otherwise.
- `SecretDetector.classify_text(str)` → SECRET for OTP/credit-card
  matches, NORMAL otherwise.
- `PerceptionFusion` applies both during fusion, so a `GroundedElement`'s
  `privacy_level` reflects the most sensitive classification among all
  its contributing sources.

## 4. Verified

`tests/unit/test_vision_privacy.py` (9 tests, pure Python) and the
end-to-end Fourth Acceptance Test in
`tests/security/test_phase3_privacy_redaction.py::test_password_field_classified_secret_via_grounding` —
a UIA-flagged password field grounds with `is_password: true` and
`privacy_level: "SECRET"` through the real API.
