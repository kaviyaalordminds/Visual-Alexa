# Input Control (Keyboard & Mouse)

## Target context is mandatory, structurally

`docs/phase-2` §16: "If target context is missing: DO NOT EXECUTE. Return
TARGET_CONTEXT_REQUIRED." This is enforced by the type system, not a
runtime check a future edit could accidentally remove:

- `computer_control.core.models.InputTarget` (used by every `keyboard.*`
  tool) has a `model_validator` that raises `ValueError` if
  `window_handle`, `window_title`, and `element_automation_id` are all
  unset — it is impossible to construct an "empty" `InputTarget`.
- `computer_control.core.selectors.UISelector` (used by every `mouse.*`
  tool) has the identical guarantee.
- `app/services/computer_control/support.py`'s `callable_executor` catches
  the resulting `pydantic.ValidationError` and maps it specifically to
  `ErrorCategory.TARGET_CONTEXT_REQUIRED` with `user_action_required=True`
  — verified end-to-end through the real HTTP API in
  `tests/integration/test_fake_backed_computer_control.py::test_keyboard_type_with_no_target_is_target_context_required`
  and the equivalent mouse test.

## No coordinate-only entry point

`computer_control.core.backends.MouseBackend`'s methods
(`move`/`click`/`double_click`/`right_click`/`scroll`) all take a
`UISelector`, never an `(x, y)` pair. The real backend
(`computer_control.windows.mouse.WindowsMouseBackend`) resolves the
selector to a pywinauto element first and lets pywinauto compute the
actual click coordinates from that element's bounding rectangle
internally — coordinates are an implementation detail of "click this
semantic thing," never a caller-supplied input. Raw coordinate clicking
is not merely deprioritized; **no tool exposing it exists** in Phase 2.

## Risk tier

Every `keyboard.*` and `mouse.*`/`ui.click`/`ui.type` tool is SENSITIVE —
input delivery can trigger arbitrary application behavior (submitting a
form, sending a message, navigating away), a materially different risk
profile from the read-only or cosmetic-window-state tools elsewhere in
Phase 2.

## Secret redaction

`app/services/computer_control/support.py` writes every tool call's
arguments to the audit log via the existing `app/services/audit.py`
redaction (fields named `password`/`secret`/`token`/`otp`/`credential`
are replaced with `[REDACTED]` before the row is written) — this applies
uniformly to `keyboard.type`'s `text` argument's sibling fields, not a
special case. Verified:
`tests/security/test_phase2_audit_redaction.py::test_keyboard_type_audit_row_redacts_a_password_argument`.
Note this redacts by *field name*, matching Phase 1's existing mechanism
exactly — it does not (and cannot, in Phase 2) inspect the *content* of a
`text` field to detect an accidentally-typed secret; that remains a
known, documented limitation (see the Phase 2 report's Known Limitations).

## Real backend vs. what's tested here

`computer_control.windows.keyboard.WindowsKeyboardBackend` and
`computer_control.windows.mouse.WindowsMouseBackend` use pywinauto's
`type_keys`/`click_input`/etc. against a resolved window/control — real,
reviewed code, not runtime-verified in this environment (see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2). The target-context and
error-mapping logic around them is fully tested against fakes.
