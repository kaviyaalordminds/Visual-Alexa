# Security Tests

## 1. Coverage against the brief's list

| Brief item | Test | Result |
|---|---|---|
| Screenshot/OCR/secret leakage | `test_phase3_privacy_redaction.py::test_password_field_classified_secret_via_grounding` | Password field classifies SECRET; no plaintext secret in the AuditLog row |
| OCR confidence never falsely upgraded | `test_phase3_privacy_redaction.py::test_ocr_confidence_never_upgraded_falsely` | Blank image yields zero regions, not fabricated low-confidence noise |
| Cloud-provider bypass | `test_phase3_prompt_injection.py::test_vision_provider_not_configured_no_cloud_upload_possible` | `vision.analyze` reports `available: false`; no network path exists to bypass |
| Unauthorized screenshot/screen access | `tests/integration/test_screen_tools_api.py` (Phase 2, still enforced), `test_vision_tools_api.py::test_target_ground_denied_when_screen_observation_disabled` | `screen_observation.enabled` gate denies by default |
| Prompt injection via visible screen text | `test_phase3_prompt_injection.py::test_malicious_screen_text_via_ocr_is_returned_as_inert_data_only` | Hostile text returned as inert `TextRegion` data only |
| Malicious on-screen text → command execution | `test_phase3_prompt_injection.py::test_grounding_never_executes_only_returns_structured_result` | Grounding a button named "Delete Everything" only ever returns data — nothing clicked |
| Tool spoofing | Structural — every tool call passes through the one `ToolRegistry`/`callable_executor`; no dynamic dispatch on caller-supplied tool names | N/A, by construction |
| Low-confidence target execution | `tests/unit/test_vision_confidence.py::test_low_confidence_requires_confirmation` | `requires_confirmation` correctly flags low scores; Phase 3 executes nothing itself |
| Ambiguous target execution | `test_vision_grounding.py::test_ambiguous_download_variants_never_guessed`, `test_vision_tools_api.py::test_target_ground_ambiguous_via_seeded_ui_tree` | `AMBIGUOUS_TARGET` returned with all candidates, `target: null` |
| Secret-region cloud upload | `test_phase3_prompt_injection.py::test_vision_provider_not_configured_no_cloud_upload_possible` | No provider configured to upload to |
| Trust-boundary correctness | `test_phase3_prompt_injection.py::test_ui_observation_is_never_a_trusted_content_source`, `::test_web_content_is_never_a_trusted_content_source`, `::test_document_content_is_never_a_trusted_content_source`, `::test_only_user_and_system_sources_are_trusted` | `TRUSTED_CONTENT_SOURCES` exactly `{USER, USER_INPUT, SYSTEM, SYSTEM_STATE}` |

## 2. Not applicable in Phase 3 (no live planner yet)

Cross-PC access, network-share perception, and remote-access attempts are
not newly relevant in this phase — Phase 3 adds no network client, no LAN
scanning, and no new network-facing surface at all; the existing
loopback-only API binding (`docs/security/03-THREAT-MODEL.md` §5) and
Phase 1/2's device-trust boundary are unchanged and unexercised by any
Phase 3 code path.

## 3. Full security test suite

`tests/security/test_phase3_prompt_injection.py` (7 tests),
`tests/security/test_phase3_privacy_redaction.py` (2 tests), plus every
pre-existing Phase 1/2 security test (`test_deny_by_default.py`,
`test_no_unrestricted_shell.py`, `test_subprocess_argv_safety.py`,
`test_phase2_*`) still passing unmodified — Phase 3 added zero new
`subprocess`/shell call sites, so the existing allowlist and AST-based
`test_subprocess_argv_safety.py` needed no changes.
