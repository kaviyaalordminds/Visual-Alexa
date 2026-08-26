# Phase 2 Test Results

Run with `bash scripts/check-python.sh` (ruff + mypy across all three
Python packages + the full pytest suite) from a clean checkout.

## Summary

```
135 passed, 1 skipped in ~24s
  tests/unit:         70 passed
  tests/integration:  35 passed, 1 skipped (screen capture live-display test — skips when $DISPLAY is unset)
  tests/security:     25 passed
  tests/agent-evals:   3 passed  (Phase 1, unchanged)
  tests/end-to-end:    2 passed  (Phase 1, unchanged)

ruff check: All checks passed (services/local-api, services/computer-control,
            packages/contracts/python, tests)
mypy:       Success, 0 issues (10 + 25 + 53 source files across the three packages)
```

The one skipped test (`test_screen_capture_succeeds_with_both_gates_satisfied`)
was independently run and confirmed passing with a real Xvfb display
active during manual verification — see below.

## What was verified live (not just via pytest), during this session

1. **Full server boot** with all 41 tools registered (1 Phase 1 +
   40 Phase 2), against a real (temp) SQLite database migrated through
   all four Alembic revisions including the two new Phase 2 migrations.
2. **The brief's own §32 functional test sequence, TEST 4–7**, executed
   against the running server via `curl`: create `Projects` folder →
   create `test.txt` → rename to `veyra-test.txt` → search for it — all
   four real, verified (`VerificationOutcome.passed: true`), chained
   correctly (each step's output path feeding the next).
3. **TEST 9** (screen capture): a real Xvfb virtual display was started,
   the Local API pointed at it via `DISPLAY`, and `screen.capture`
   invoked through the API — returned a real 640×480 PNG (1296 base64
   characters). Also exercised through the **actual desktop shell UI**
   (Playwright driving the real Vite dev server + running Tauri-shell
   frontend), screenshotted, and confirmed rendering `Computer Control:
   CONNECTED` on the status screen and a `SUCCESS`/`EXECUTED` result in
   the developer console after enabling both required settings.
4. **TEST 10, 11, 12**: `filesystem.delete`, `system.execute` → HTTP 404
   (not registered at all); `/etc/passwd` access → `PATH_PROTECTED`.
5. **`PLATFORM_NOT_SUPPORTED` path**, live: `application.list_running`
   invoked on this Linux host returned a structured
   `PLATFORM_NOT_SUPPORTED` failure — proving the platform gate fires
   correctly rather than crashing or hanging.
6. **The `computer_control.enabled` gate**, live: with the setting at its
   real seeded default (`False`), every Phase 2 tool was confirmed
   blocked; flipping it via `PATCH /settings/computer_control.enabled`
   was confirmed to unblock them immediately (no restart needed).
7. **Lazy Windows-import architecture**, live: `import computer_control.windows.applications`
   (and every sibling module) confirmed to succeed on this Linux host
   despite `pywinauto`/`pywin32` not being installed here — proving the
   "never import at module level" discipline actually holds, not just by
   code review.
8. **Desktop shell build**: `npm run build` (tsc + vite) and `eslint .`
   both clean after adding the developer console and its TypeScript
   contracts.

## What was not, and could not be, verified here

Real Windows UI Automation/Win32 behavior — `pywinauto`/`pywin32` do not
run on Linux, and this container has no Windows kernel. Every
`computer_control.windows.*` module is real, reviewed implementation code
(confirmed to at least import correctly, and manually checked against the
documented `pywinauto` API surface) but its actual runtime correctness
against a real Notepad/Calculator/File Explorer window has not been
exercised. This is the same category of limitation Phase 1 disclosed for
the desktop shell's Windows/WebView2 path, applied to a larger surface
area — see `docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2 for the full
reasoning, and the Phase 2 final report's Known Limitations for what this
means for a reviewer deciding what still needs Windows-hardware
validation before Phase 3.
