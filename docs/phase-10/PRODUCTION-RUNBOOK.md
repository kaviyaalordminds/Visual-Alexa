# VEYRA Production Runbook

Every command below was run for real this session unless marked
otherwise. Windows-specific commands are written for Windows but could
not be executed from this Linux sandbox — noted where relevant.

## How to start VEYRA

**Development** (source checkout):
```
scripts\dev-backend.bat
cd apps\desktop && npm run dev
```
or, in one step: `scripts\start-veyra.bat`.

**Production** (once a Windows build exists — see PACKAGING below): run
the installed `VEYRA.exe`. The desktop shell spawns its own Local API
sidecar (`apps/desktop/src-tauri/src/lib.rs`) — nothing else to start
manually.

## How to stop VEYRA

**Development**: Ctrl+C in the backend's terminal, or close the
`dev-backend.bat` window.

**Production**: close the VEYRA window. The shell's `on_window_event`
handler stops the sidecar; the backend's own shutdown sequence (verified
live this session) runs: stop accepting new WebSocket frames -> close
every open `/events` connection -> close any launched browser -> dispose
the database engine -> flush logs -> exit.

## How to restart VEYRA

Stop, then start again, exactly as above. No special restart command
exists or is needed — every startup step (migrations, tool registration)
is idempotent (verified in `tests/unit/test_database_migrate.py` and
exercised live every time the backend has been started this session).

## How to diagnose failures

1. `curl http://127.0.0.1:8756/health` — is the process alive at all?
2. `curl http://127.0.0.1:8756/ready` — has startup actually finished?
   (503 while starting, 200 once real.)
3. `curl http://127.0.0.1:8756/system` — full per-subsystem status, each
   with a `details` reason string explaining exactly why it isn't
   CONNECTED, if it isn't. Also carries `version`/`uptime_seconds`.
4. Inspect the log file (see below) for the exact `[VEYRA]`/`[AI]`/
   `[VOICE]`/`[VISION]`/`[COMPUTER]`/`[DEVICE]` startup sequence, or a
   `[VEYRA] STARTUP FAILED` / `Reason` / `Resolution` block if startup
   itself failed.

## How to inspect logs

Logs live under the app-data directory (`app/core/paths.py::
resolve_app_data_dir()`), never inside the install/source directory:

- Windows: `%APPDATA%\VEYRA\logs\local-api.log`
- macOS: `~/Library/Application Support/VEYRA/logs/local-api.log`
- Linux: `$XDG_DATA_HOME/veyra/logs/local-api.log` (or
  `~/.local/share/veyra/logs/local-api.log`)

Rotates at 10 MiB, keeps 5 backups (`local-api.log.1` … `.5`) — verified
live this session (a real log file was created and written to at exactly
this path under a test `VEYRA_APP_DATA_DIR`). Every line is one JSON
object (`timestamp`, `level`, `logger`, `message`, `correlation_id`).

## How to repair the database

The database migrates itself automatically and safely on every startup
(`app/db/migrate.py::ensure_database_ready()`) — this is not something an
operator normally needs to do manually. If startup itself reports
`[VEYRA] STARTUP FAILED` with a `MIGRATION_ERROR`-class reason: the
database file is never deleted or altered destructively by this process
(verified: `ensure_database_ready()` has no code path that drops data —
`tests/unit/test_database_migrate.py::test_stale_database_is_upgraded_
without_losing_existing_data`). Inspect the named migration in
`database/migrations/versions/` and the database file directly before
considering any manual change — never hand-edit the schema
(CLAUDE.md: "never hand-edit the database file or apply ad hoc DDL").

## How to reset configuration

Delete or edit the `.env` file (development) or the relevant
`VEYRA_*` environment variables (production/service configuration).
There is no in-app "reset to defaults" — Settings values fall back to the
documented defaults in `app/core/config.py` / `.env.example` the moment
an override is removed.

## How to recover from corruption

1. Stop VEYRA.
2. Move (don't delete) the app-data directory's `database/veyra.db`
   aside.
3. Start VEYRA — a fresh, fully-migrated database is created
   automatically (verified live this session, and in
   `tests/unit/test_database_migrate.py::
   test_fresh_database_is_created_and_migrated_to_head`).
4. There is currently no backup/restore mechanism (confirmed absent,
   `docs/phase-10/SECURITY-AUDIT.md` §6) — moving the old file aside
   preserves it for manual inspection, but nothing automatically merges
   its data back in.

## How to uninstall / reinstall

Not yet testable from this sandbox (no Windows installer has been built
— see `RELEASE-CHECKLIST.md`). Once one exists: the standard Windows
"Apps & Features" uninstall removes the installed binaries; the app-data
directory (database, credentials, logs) is intentionally left behind on
uninstall (standard Windows convention — a reinstall picks the same data
back up) unless the user explicitly deletes
`%APPDATA%\VEYRA\` themselves.

## Troubleshooting commands (Part 60)

| Need | Command |
|---|---|
| Health check | `curl http://127.0.0.1:8756/health` |
| Readiness | `curl http://127.0.0.1:8756/ready` |
| Full diagnostics | `curl http://127.0.0.1:8756/system` |
| Service status (dev) | `scripts\start-veyra.bat`'s own health-poll output |
| Database migration state | `cd database && alembic current` |
| Apply migrations manually | `cd database && alembic upgrade head` (normally automatic) |
| Log collection | copy the app-data `logs/` directory |
| Build (backend sidecar, Windows only) | `python scripts\build-backend-sidecar.py` |
| Build (desktop shell) | `cd apps\desktop && npm run build` / `cargo tauri build` |
| Test (Python) | `bash scripts/check-python.sh` |
| Test (frontend) | `cd apps\desktop && npx vitest run && npx eslint . && npx tsc -b` |
| Package | `cd apps\desktop && cargo tauri build` (after the sidecar build above) |
