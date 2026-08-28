# Phase 10 — Release Checklist

Checked items below were verified live this session (backend started
against a real, isolated app-data directory; endpoints hit for real;
process sent a real SIGTERM and observed to exit cleanly). Unchecked
items require a real Windows machine this Linux sandbox cannot provide —
each names exactly what's blocking it.

- [x] tests pass — 766 backend (`scripts/check-python.sh`), 69 frontend
      (`npx vitest run`), ruff/mypy/eslint/tsc all clean.
- [x] security tests pass — `tests/security/` (part of the 766 above);
      no regressions from this phase's changes.
- [x] database migrations work — `ensure_database_ready()` verified live
      against a fresh, isolated app-data DB (revision `2a025fb1f8a8`
      reached from scratch); already regression-tested since Phase 9.
- [ ] clean installation works — no Windows installer has been built or
      run; blocked on a Windows machine to run
      `scripts/build-backend-sidecar.py` + `cargo tauri build`.
- [ ] clean uninstall works — same blocker; nothing to uninstall yet.
- [x] startup works — verified live: real structured `[VEYRA]`/`[AI]`/
      `[VOICE]`/`[VISION]`/`[COMPUTER]`/`[DEVICE]` logs, `/health` and
      `/ready` both live within 1s.
- [x] shutdown works — verified live: real SIGTERM, `[VEYRA] Shutting
      down` -> WebSocket close-all -> browser close -> DB engine dispose
      -> `[VEYRA] Local API: STOPPED`, process exits with no lingering PID.
- [ ] restart works — startup and shutdown are each independently
      verified; a full stop-then-start-again cycle on a packaged build
      (sidecar restart via the desktop shell) has not been exercised —
      needs Windows.
- [ ] service recovery works — no process supervisor exists yet (P1,
      still open per `RELEASE-READINESS.md`); a crashed Local API does
      not currently restart itself.
- [x] frontend works — 69 tests passing, real backend integration
      verified via `tests/integration/`, `tsc`/`eslint` clean.
- [x] backend works — 766 tests passing, live-verified this session.
- [x] AI works (as far as this build implements it) — real
      `CloudLLMProvider` + health-check tool, honestly reports NOT
      CONFIGURED/DEGRADED/CONNECTED/ERROR; verified live and by test.
      A real LLM-backed planner does not exist (documented, out of
      scope — see `docs/subsystem-activation/AI-STATUS.md`).
- [x] voice works (as far as this build implements it) — honestly
      reports NOT CONFIGURED; no real audio pipeline exists (documented,
      out of scope).
- [x] avatar works — event-driven, verified in Phase 6/9; unchanged
      this phase.
- [x] computer control works (as far as this platform allows) —
      verified live: real platform detection reports NOT ENABLED/
      DISABLED honestly on this non-Windows sandbox; real Win32/UIA
      backends exist and are exercised by `tests/`.
- [x] browser control works — Playwright-based, verified since Phase 8;
      unchanged this phase.
- [x] permissions work — Policy Engine unchanged and still fully tested;
      CRITICAL-tier non-bypassability re-verified in Phase 9/10 audits.
- [x] confirmation works — `ConfirmationManager` unchanged, still tested.
- [x] logs work — verified live: real rotating JSON log file created
      under the app-data directory, real content confirmed.
- [x] diagnostics work — `/system` now reports real per-subsystem status
      plus `version`/`uptime_seconds`; `/ready` distinct from `/health`;
      verified live.
- [x] no secrets committed — re-confirmed: no `.env` file tracked, no
      hardcoded credential literal found anywhere in the repo (repeated
      across Phase 9 and Phase 10 audits).
- [ ] production build works — blocked on a Windows machine: the sidecar
      binary must be built there (PyInstaller doesn't cross-compile) and
      `cargo tauri build` must produce and be tested against a real
      `.exe`/`.msi`.

## What would unblock every remaining item

One Windows machine (or Windows CI runner) to: (1) run
`scripts/build-backend-sidecar.py`, (2) run `cargo tauri build`, (3)
install the resulting `.msi`/`.exe`, (4) run through this checklist's
remaining rows against that real install. Everything on the Python/Rust/
TypeScript side that could be verified without one has been.
