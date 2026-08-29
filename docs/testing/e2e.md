# End-to-End Task Tests

Phase 13's spec named five specific end-to-end scenarios: "Open
Notepad," "Open Chrome," "Find project.pdf," "Create a folder called
VEYRA-Test," and "Open Chrome and search YouTube for AR Rahman songs."
This document maps each to its real, currently-running test coverage
through the full `intent -> planner -> orchestrator -> tool_execution ->
verification` chain (no monkeypatched plans, unless noted) — and is
honest about the one gap found and closed this phase.

| Scenario | Coverage | Notes |
|---|---|---|
| "Open Notepad" | `tests/unit/test_agent_planner.py::test_open_application_plans_launch_and_verify`, `tests/unit/test_agent_intent.py::test_open_application_understood` | Plans `application.launch` + `window.get_active`. This sandbox has no `ApplicationBackend` outside Windows, so a live run here reports `PLATFORM_NOT_SUPPORTED` honestly rather than faking success — see `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2`. |
| "Open Chrome" | `tests/unit/test_agent_planner.py::test_browser_task_with_web_search_plans_launch_search_and_observe`, `tests/integration/test_agent_tasks_api.py::test_browser_task_search_completes_for_real` | The integration test runs for real against the Playwright-backed browser engine (Phase 8). |
| "Find project.pdf" | `tests/unit/test_agent_planner.py::test_search_files_plans_one_step_per_root`, `tests/integration/test_agent_tasks_api.py::test_search_files_completes_for_real` | The integration test creates a real file in the sandboxed filesystem root and confirms the task actually finds it. |
| "Create a folder called VEYRA-Test" | `tests/unit/test_agent_intent.py::test_create_folder_understood`, `tests/unit/test_agent_planner.py::test_create_folder_plans_a_single_verified_step`, `tests/integration/test_agent_tasks_api.py::test_create_folder_completes_for_real` | **A real gap closed this phase** (`docs/phase-13-audit.md`): `filesystem.create_folder` has been a real, registered tool since Phase 2, but nothing routed natural-language "create a folder ..." requests to it — any such request returned `MISSING_INFORMATION`. `IntentInterpreter`/`TaskPlanner` now recognize it. Because the tool is `MODERATE` risk, the real end-to-end test goes through the real `WAITING_PERMISSION` → `POST /confirm` flow, then asserts the folder actually exists on disk — see `docs/security/permissions.md`. |
| "Open Chrome and search YouTube for AR Rahman songs" | `tests/unit/test_agent_planner.py::test_browser_task_with_web_search_plans_launch_search_and_observe` (query-extraction logic) | The planner's web-search template is search-engine generic (`browser.search`, engine `"google"`); it does not special-case youtube.com, so "search YouTube for X" plans as a general web search for that query rather than a YouTube-specific search. Genuinely capable of the "open a browser and search for something" shape; the YouTube-specific site behavior is not separately implemented and is not claimed here. |

## Where honest capability errors are expected, not a bug

- **`open_application` on this Linux sandbox**: `PLATFORM_NOT_SUPPORTED`,
  not `COMPLETED` — there is no real `ApplicationBackend` outside
  Windows, so this is a correct, honest report, not a broken test
  (`tests/unit/test_application_registry.py`).
- **`delete_files`**: always `CAPABILITY_UNAVAILABLE` — no delete tool is
  registered, by design, matching CLAUDE.md's "no destructive operations
  without explicit confirmation" combined with there being no
  implemented delete action to confirm.
- **`send_file` / `control_device` on a remote machine**:
  `CAPABILITY_UNAVAILABLE` / refused respectively — no real messaging
  integration exists yet (Phase 8 Stop Condition), and remote-device
  requests are refused before planning even starts
  (`docs/security/04-DEVICE-TRUST.md`).

## Running these tests

```bash
cd services/local-api
python -m pytest ../../tests/unit/test_agent_intent.py \
                  ../../tests/unit/test_agent_planner.py \
                  ../../tests/integration/test_agent_tasks_api.py -v
```

Or the full suite via `scripts/check-python.sh` from the repo root
(ruff + mypy across every Python package, then the full pytest suite).

## Manual, human-in-the-loop verification

`apps/desktop/src/tasks/TaskPanel.tsx` (Phase 13 P0-5) is the real place
to drive any of the five scenarios by hand against a running backend:
type the request, click **Run Task**, watch live step progress, and
approve/deny any real confirmation prompt that appears. See
`docs/development/runbook.md` for how to start both processes.
