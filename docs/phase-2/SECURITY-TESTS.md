# Security Tests

Maps the brief's §30 required test list to the actual test files, all
passing in this environment.

| # | Brief requirement | Test file | Notes |
|---|---|---|---|
| 1 | Path traversal | `tests/unit/test_path_policy.py::test_traversal_outside_allowed_root_is_denied`, `tests/security/test_phase2_path_security_api.py::test_traversal_via_search_directory_is_denied` | Against a real filesystem and the real HTTP API |
| 2 | Protected path access | `tests/unit/test_path_policy.py::test_posix_protected_paths_are_denied` (parametrized), `tests/security/test_phase2_path_security_api.py::test_get_metadata_on_protected_path_is_denied` | |
| 3 | UNC paths | `tests/unit/test_path_policy.py::test_unc_and_device_paths_are_denied`, `tests/security/test_phase2_path_security_api.py::test_unc_path_is_denied` | |
| 4 | Network shares | Covered by the UNC test (`\\server\share`) and the protocol-path test (`smb://...`) | No separate mounted-share concept exists to test beyond path syntax |
| 5 | Invalid executables | `tests/unit/test_application_registry.py::test_unresolvable_executable_raises_not_found` | |
| 6 | Unauthorized application launch | `tests/unit/test_application_registry.py::test_unknown_application_is_denied`, `test_disabled_application_is_denied_even_though_registered`, `tests/integration/test_fake_backed_computer_control.py::test_application_launch_of_unknown_app_is_denied` | |
| 7 | Unauthorized keyboard input | `tests/integration/test_fake_backed_computer_control.py::test_keyboard_type_with_no_target_is_target_context_required` | No grant/target = no execution |
| 8 | Unauthorized mouse input | `tests/integration/test_fake_backed_computer_control.py::test_mouse_click_with_no_selector_criteria_is_target_context_required` | |
| 9 | Unauthorized screen capture | `tests/integration/test_screen_tools_api.py` (both denial tests) | Two independent gates, both tested |
| 10 | Permission bypass | `tests/security/test_phase2_deny_by_default.py::test_computer_control_disabled_by_default_blocks_every_phase2_tool`, all the `PERMISSION_DENIED` assertions throughout `tests/integration/` | |
| 11 | Tool spoofing | `tests/security/test_phase2_deny_by_default.py::test_dangerous_tool_is_not_registered` (404 for `filesystem.delete`, `process.terminate`, `system.execute`, etc.) | |
| 12 | Invalid tool arguments | `tests/integration/test_tasks_api.py`-style 422s (Phase 1, still applies); Phase 2: malformed `UISelector`/`InputTarget` → `TARGET_CONTEXT_REQUIRED` | |
| 13 | Timeout bypass | `tests/unit/test_wait_for_element.py::test_times_out_if_element_never_appears` | |
| 14 | Cancellation failure | `tests/unit/test_wait_for_element.py::test_cancellation_interrupts_the_wait_immediately` | Real `asyncio.CancelledError`, not a flag |
| 15 | Audit-log secret leakage | `tests/security/test_phase2_audit_redaction.py::test_keyboard_type_audit_row_redacts_a_password_argument` | |
| 16 | Prompt-injection tool attempts | Inherited from Phase 1's `tests/security/test_permission_bypass.py` (the Policy Engine never trusts a caller's stated justification); no Phase 2 tool interprets any argument as an instruction rather than data | |

## Additional Phase 2-specific security tests (beyond the brief's list)

- `tests/security/test_no_unrestricted_shell.py` (narrowed, not weakened —
  see below) + `tests/security/test_subprocess_argv_safety.py` (new,
  precise) — together prove no shell string execution exists anywhere,
  and the two legitimate `subprocess` call sites use list-argv/`shell=False`.
- `tests/security/test_phase2_deny_by_default.py::test_no_registered_tool_accepts_a_free_form_shell_command_argument` —
  no tool's JSON schema exposes a raw `command` field, present or future.

## The one architecture conflict this phase surfaced (and resolved deliberately)

Phase 1's `test_no_unrestricted_shell.py` banned the substring
`subprocess.` anywhere in application code — correct for Phase 1, where no
tool needed to spawn a process. `application.launch` legitimately needs
to (brief §19 explicitly endorses "a specific strongly typed tool" that
does this). The test was narrowed to an **allowlist of exactly two
reviewed files** (`computer_control/windows/applications.py`,
`computer_control/launcher.py`) instead of removing the ban outright, and
`test_subprocess_argv_safety.py` was added to statically parse those two
files' `subprocess.*` calls via `ast` and assert the first argument is a
list literal and `shell` is never `True` — a **stronger**, more precise
guarantee than the blanket string-ban it replaced for those two sites.
Documented in full in
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §5.
