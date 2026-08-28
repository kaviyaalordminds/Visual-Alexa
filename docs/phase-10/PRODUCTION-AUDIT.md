# Phase 10 — Production Audit

Status: audit only (Phase 10 Part 1). Produced by direct code inspection
in the sandbox this session runs in — a Linux container with no Windows
host, no real microphone/GPU, and no way to build or run an actual
`.exe`/`.msi`. Findings below are evidence-based; anything that requires a
real Windows machine to verify is flagged as such rather than guessed at.

This audit intentionally does not repeat `docs/PHASE-9-AUDIT.md`'s
findings (backend startup/migrations, tool registry, policy engine,
orchestrator, browser engine, IoT pairing, frontend↔backend endpoint
parity — all already covered there and already fixed where they were
broken). It covers only what Phase 9 didn't: packaging, process
supervision, build/release tooling, and a second security pass.

## Current architecture (as shipped today)

One FastAPI process (`services/local-api`) in-process-imports
`computer_control`, `vision`, `voice`; `services/ai-runtime` and
`services/device-gateway` are placeholder directories (README only — the
real logic lives in `app/services/agent/` and `app/services/mock_iot.py`
respectively). One Tauri/React desktop shell talks to that process over
plain HTTP/WebSocket at `127.0.0.1:8756`. One SQLite database
(`database/veyra.db`), Alembic-migrated automatically at startup (Phase 9).

## Current services / ports / processes

| Process | Owns | Port | Started by |
|---|---|---|---|
| Local API (`uvicorn app.main:app`) | DB, tool registry, policy engine, orchestrator, all domain tools | `127.0.0.1:8756` | manually, via `scripts/dev-backend.bat` or a bare `uvicorn` command |
| Desktop shell (Tauri/WebView) | UI only | n/a (loads `http://127.0.0.1:8756`/`ws://.../events`) | `npm run dev` (dev) / the packaged `.exe` (prod, once one exists) |

No other process exists. `services/ai-runtime` and `services/device-gateway`
never run as separate processes — this is deliberate, not a gap (Phase 1's
placeholder-package pattern), but confirms there is nothing to "start" for
either beyond what already runs inside the Local API.

## Communication between services

HTTP + WebSocket only, both over loopback. No IPC, no shared memory, no
message broker. In-process Python calls between the Local API and
`computer_control`/`vision`/`voice` (plain imports, not RPC).

## Startup sequence (current, real)

`app.main.lifespan()`: configure logging → `ensure_database_ready()`
(Alembic, Phase 9) → register tools → load application registry → build
computer-control/vision bundles → register browser/IoT tools →
`reconnect_all_on_startup` (now fault-isolated, Phase 9 P1-1) → init
orchestrator → init voice manager → `[VEYRA] Local API: READY`. This is
one process's internal sequence — there is no cross-process dependency
ordering today because there is only one long-running process.

## Shutdown sequence (current, real)

`app.main.lifespan()`, after `yield`: **exactly one step** —
`await browser_manager.close_all()`. No explicit stop-accepting-requests
step, no explicit WebSocket close-all, no explicit DB engine `dispose()`,
no explicit log flush. The Rust desktop shell (`src-tauri/src/lib.rs`) has
no window-close handler at all — closing the window doesn't signal the
backend to shut down; the backend only stops if its own process is killed
independently.

## Failure scenarios — what actually happens today

- **Local API process crashes**: nothing restarts it. No supervisor,
  systemd unit, `pm2`, or watchdog exists anywhere in the repo. It stays
  dead until a human notices and re-runs the start script.
- **A launched browser session crashes**: `BrowserManager` marks the
  session `CRASHED` but never auto-relaunches it — every subsequent tool
  call against that `session_id` just fails again until the caller opens a
  brand-new session (`browser.launch`).
- **Port 8756 already in use**: no pre-flight check anywhere; `uvicorn`
  raises an uncaught `OSError`, the dev script's window shows a raw
  traceback, and `start-veyra.bat`'s health poll just times out after 30s
  with a generic message — it never diagnoses "port in use" specifically.
- **A second VEYRA instance started concurrently**: nothing detects this
  (no PID file, no lock file anywhere in `services/local-api`) — it would
  fail at the same uvicorn bind step, again with no VEYRA-specific
  diagnostic.
- **No visible console (a packaged app launched by double-click)**: all
  logging goes to `sys.stdout` only (`app/core/logging.py` — a single
  `StreamHandler(sys.stdout)`, no file handler, no rotation). With no
  attached console, every log line is simply discarded — there would be
  no log file to inspect after a crash.

## Security boundaries (re-verified this pass, see SECURITY-AUDIT.md for detail)

Confirmed still correct: loopback-only default bind, CORS allowlist (no
wildcard), path-traversal protection is real and uses `Path.resolve()` +
`is_relative_to()` (not naive prefix matching — correctly defeats `../`,
absolute-path, UNC, and malicious-symlink cases), every subprocess call in
the repo is `shell=False` with either a fixed allowlisted command or a
pre-validated path (three call sites total, all compliant), prompt-injection
defense is a real, wired mechanism (`WebContentSanitizer` +
`InstructionBoundary.tag()`, actually called from the browser tools' text
extraction path, not just documentation). Plugin "sandboxing" is
permission-flags only — a plugin executor runs with full in-process Python
privilege, no OS-level isolation; this is an honest architectural
limitation to carry forward, not a bug to silently claim fixed.

## Known technical debt / incomplete features (new-to-Phase-10 items only)

1. No process supervisor for the Local API (crash = stays dead).
2. No packaging mechanism bundles the Python backend into the Tauri build
   at all — `cargo tauri build` today would produce a shell with nothing
   behind it (see ARCHITECTURE-AUDIT.md).
3. No log file / rotation — logs vanish with no console attached.
4. No `/ready` endpoint (only `/health` liveness and `/system` full status).
5. No CI pipeline exists (no `.github/` directory at all).
6. No version reporting endpoint (the FastAPI `version="0.1.0"` only
   surfaces in `/openapi.json`, and is a second hand-maintained literal,
   not read from any `pyproject.toml`).
7. Frontend: no error boundary anywhere — an uncaught render exception
   white-screens the whole app.
8. Frontend: `App.tsx`'s 5s `/system` poll has no in-flight/ordering guard
   — a slow response can overwrite a newer one (stale-response race).
9. No backup/restore mechanism for local state (DB, credentials store).

## Production blockers (the subset of the above that block "install and
run on a real Windows PC" specifically — see ARCHITECTURE-AUDIT.md for
full detail)

- No sidecar/process-spawn mechanism exists for Tauri to start the Python
  backend — a packaged `VEYRA.exe` today would open a WebView pointed at
  a backend that isn't running.
- All data paths (`database/veyra.db`, credentials store, browser
  downloads) resolve relative to the source-tree location of
  `config.py`, not a Windows per-user `%APPDATA%` location — wrong for an
  installed `C:\Program Files\VEYRA\` deployment (write-protected,
  not multi-user-safe).

These two are the hard blockers standing between "works in dev mode" and
"installable Windows application," and are architecture-level, not
one-line fixes — see RELEASE-READINESS.md for prioritization.
