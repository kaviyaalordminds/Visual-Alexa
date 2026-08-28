# Phase 10 — Release Readiness

Consolidated, prioritized findings from `PRODUCTION-AUDIT.md`,
`ARCHITECTURE-AUDIT.md`, `SECURITY-AUDIT.md`, `DEPENDENCY-AUDIT.md`, and
`TESTING-AUDIT.md`. No P0s block *development-mode* operation — Phase 9
already closed those. Everything below is what stands between today's
dev-mode app and an installable Windows production build.

## P0 — blocks "install and run on a real Windows PC" specifically

1. **No mechanism spawns the Python backend from the packaged desktop
   app.** No Tauri sidecar/`externalBin`, no `tauri-plugin-shell`, no
   `std::process::Command` anywhere in `src-tauri/`. A packaged
   `VEYRA.exe` today opens a WebView pointed at a backend that doesn't
   exist. This is the single hardest blocker in the whole audit.
2. **All local data paths resolve into the source tree, not
   `%APPDATA%`.** Wrong for an installed, admin-directory deployment;
   not multi-user-safe.

## P1 — real reliability/operability gaps for a production deployment

3. No process supervisor — a crashed Local API stays dead until a human
   notices; no PID/lock file even detects a stale/duplicate instance.
4. No log file or rotation — logs go to stdout only, which vanishes with
   no attached console (the normal case for a double-clicked app).
5. Shutdown does one thing (`browser_manager.close_all()`) — no explicit
   WebSocket close-all, DB `dispose()`, or log flush.
6. No `/ready` endpoint (only `/health` liveness + `/system` full status)
   and no dedicated version-reporting endpoint (the one `version="0.1.0"`
   that exists is a second, hand-maintained literal, not sourced from any
   `pyproject.toml`).
7. Frontend: no error boundary — a single bad render blanks the whole app.
8. Frontend: a real stale-response race in the 5s `/system` poll.
9. No CI pipeline exists at all.

## P2 — real but lower urgency

10. No system tray, no "start with Windows," no updater — all confirmed
    absent, all expected gaps for this phase, all real work for a later
    pass.
11. No backup/restore mechanism for local state.
12. Plugin execution has no OS-level sandbox (permission-flags only).
13. Frontend loading/error/empty states are conflated across the three
    main panels; accessibility attributes are sparse outside the avatar.
14. No single root-level command runs the full Python + frontend check
    suite together.

## What was NOT attempted this pass, and why

This audit's own findings (P0 #1 and #2 especially) require substantial,
carefully-scoped implementation work — a real Rust sidecar-process
integration, Windows-app-data-relative path resolution with a dev-mode
override, a process supervisor design — that deserves its own focused
implementation pass rather than being rushed alongside a 60+ section
audit request. Immediately after this audit was produced, a new, more
specific and immediately actionable request arrived (VEYRA core subsystem
activation: real AI/Voice/Vision/Computer-Control/IoT health checks) and
was prioritized for implementation in this same session — see the git
history and `docs/subsystem-activation/` for that work. The P0/P1 items
above remain open and are the recommended target for the next dedicated
Phase 10 implementation pass.

## What this sandbox cannot verify, ever, without a real Windows host

Building/running a real `.exe`/`.msi`, WebView2 provisioning behavior, a
genuine clean-machine install/uninstall test, system tray behavior, and
autostart registry integration. Any future claim that these "work" must
come from an actual Windows test, not from this environment.
