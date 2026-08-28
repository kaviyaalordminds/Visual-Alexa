@echo off
setlocal enabledelayedexpansion

rem VEYRA Local API — Windows development startup.
rem docs/architecture/01-SYSTEM-ARCHITECTURE.md, CLAUDE.md ("The Local
rem API binds to loopback (127.0.0.1) only").
rem
rem Fails loudly and stops on the first real problem — never silently
rem swallows an error and reports READY anyway.

cd /d "%~dp0.."

echo [VEYRA] Starting Local API (development)

if not exist ".venv\Scripts\activate.bat" (
    echo [VEYRA] No .venv found — creating one...
    python -m venv .venv
    if errorlevel 1 (
        echo [VEYRA] STARTUP FAILED
        echo [VEYRA] Reason: "python -m venv .venv" failed.
        echo [VEYRA] Resolution: install Python 3.11+ and ensure "python" is on PATH.
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [VEYRA] STARTUP FAILED
    echo [VEYRA] Reason: could not activate .venv.
    exit /b 1
)

python -c "import fastapi, sqlalchemy, alembic, aiosqlite" 2>nul
if errorlevel 1 (
    echo [VEYRA] Installing/updating dependencies...
    pip install -e packages\contracts\python
    if errorlevel 1 goto :dep_fail
    pip install -e "services\local-api[dev]"
    if errorlevel 1 goto :dep_fail
)
goto :deps_ok

:dep_fail
echo [VEYRA] STARTUP FAILED
echo [VEYRA] Reason: dependency install failed — see pip output above.
exit /b 1

:deps_ok
rem Database migrations also run automatically at app startup
rem (app/db/migrate.py::ensure_database_ready) — running them here too is
rem belt-and-braces so a migration failure is caught before uvicorn even
rem starts, with output the developer can act on immediately.
echo [VEYRA] Applying database migrations...
pushd database
alembic upgrade head
if errorlevel 1 (
    popd
    echo [VEYRA] STARTUP FAILED
    echo [VEYRA] Reason: Alembic migration failed — see output above.
    echo [VEYRA] Resolution: fix the failing migration; the database file is never deleted by this step.
    exit /b 1
)
popd

echo.
echo VEYRA
echo -------------------------
echo Local API: http://127.0.0.1:8756
echo WebSocket: ws://127.0.0.1:8756/events
echo Database:  SQLite (database\veyra.db)
echo Environment: development
echo Status: STARTING (see structured logs below for READY)
echo -------------------------
echo.

cd services\local-api
uvicorn app.main:app --host 127.0.0.1 --port 8756

endlocal
