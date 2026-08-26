# Security Tests

## 1. Coverage against brief §88

| # | Item | Test | Result |
|---|---|---|---|
| 1 | Tool bypass | `test_agent_adversarial.py::test_hallucinated_tool_is_rejected_never_executed` | `UNKNOWN_TOOL`, never executed |
| 2 | Policy bypass | `test_agent_adversarial.py::test_moderate_action_without_grant_is_denied_not_executed` | Pauses at `WAITING_PERMISSION`, filesystem effect never happens |
| 3 | Confirmation bypass | `test_agent_tasks_api.py::test_confirmation_denial_cancels_without_acting` | `DENY` → `CANCELLED`, nothing executed |
| 4 | Invalid tool | Same as #1 | — |
| 5 | Invalid arguments | Reused from Phase 2 (`ValidationError` → `TARGET_CONTEXT_REQUIRED`, unchanged) | — |
| 6 | Prompt injection | `test_agent_adversarial.py::test_adversarial_phrases_never_reach_planning` | `UNSAFE`, zero tool calls |
| 7 | Web content injection | Structural absence — see `PROMPT-INJECTION.md` §1 | N/A, no bridge exists yet |
| 8 | Document injection | Structural absence — see `PROMPT-INJECTION.md` §3 | N/A, no capability exists yet |
| 9 | Secret leakage | Reused from Phase 1 audit redaction (unchanged) — see `AUDIT.md` §2 | — |
| 10 | Unauthorized file deletion | `delete_files` always `CAPABILITY_UNAVAILABLE` — no delete tool exists at all | — |
| 11 | Unauthorized shell execution | `tests/security/test_no_unrestricted_shell.py` (Phase 1/2, still passing, zero new call sites) | — |
| 12 | Remote access attempt | N/A — no network-facing surface added | — |
| 13 | LAN discovery attempt | N/A — `control_device`/`browser_task` are `CAPABILITY_UNAVAILABLE` before any network code runs | — |
| 14 | Infinite retry | `test_agent_adversarial.py::test_infinite_retry_is_bounded_by_budget_never_hangs` | Terminal state within budget |
| 15 | Infinite replan | `LoopBudgetTracker.budget_exceeded_reason` — `max_replans` check, unit-tested | — |
| 16 | Fake tool result | Structural — `AgentOrchestrator` never constructs an `ActionResult` itself, only ever consumes `execute_tool_call`'s real return | — |
| 17 | Fake success | `test_agent_adversarial.py::test_fake_success_never_overrides_real_tool_failure` | Task `FAILED` despite a lying step description |
| 18 | Task cancellation | `test_agent_adversarial.py::test_cancellation_mid_plan_stops_remaining_steps` | `CANCELLED`, `current_step < total_steps` |
| 19 | Permission denial | Same as #2 | — |
| 20 | Model timeout | N/A — no model is called (`NotConfiguredLLMProvider`), so there is nothing to time out |

## 2. Full Phase 4 security suite

`tests/security/test_agent_adversarial.py` — 6 tests, all against the
real HTTP API, real Policy Engine, real filesystem sandbox. Every
pre-existing Phase 1-3 security test still passes unmodified (280 total
in the full suite) — Phase 4 introduced zero new `subprocess`/shell call
sites, so `test_no_unrestricted_shell.py`/`test_subprocess_argv_safety.py`
needed no changes.
