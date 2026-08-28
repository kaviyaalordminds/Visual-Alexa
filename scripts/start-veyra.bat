@echo off
setlocal enabledelayedexpansion

rem VEYRA — starts the Local API (in a new window) and the desktop
rem frontend's Vite dev server, then polls /health until the backend is
rem actually ready before declaring READY. Never reports READY on a
rem guess — a backend that never comes up is reported as such.

cd /d "%~dp0.."

echo [VEYRA] Launching Local API...
start "VEYRA Local API" cmd /k "%~dp0dev-backend.bat"

echo [VEYRA] Launching frontend (Vite dev server)...
start "VEYRA Frontend" cmd /k "cd /d "%~dp0..\apps\desktop" && npm run dev"

echo [VEYRA] Waiting for Local API to become healthy...
set /a _attempts=0

:poll
set /a _attempts+=1
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8756/health > "%TEMP%\veyra_health.txt" 2>nul
set /p _status=<"%TEMP%\veyra_health.txt"
if "%_status%"=="200" goto :ready
if %_attempts% GEQ 30 goto :timeout
timeout /t 1 /nobreak >nul
goto :poll

:timeout
echo.
echo [VEYRA] STARTUP FAILED
echo [VEYRA] Reason: Local API did not respond healthy at http://127.0.0.1:8756/health within 30s.
echo [VEYRA] Resolution: check the "VEYRA Local API" window for the actual error (commonly a
echo [VEYRA]             database/migration failure — see database/veyra.db and database/migrations).
exit /b 1

:ready
echo.
echo VEYRA
echo -------------------------
echo Local API: http://127.0.0.1:8756
echo WebSocket: ws://127.0.0.1:8756/events
echo Frontend:  http://localhost:1420
echo Database:  SQLite
echo Environment: development
echo Status: READY
echo -------------------------
echo.
echo Both services are running in their own windows. Close those windows
echo (or Ctrl+C inside them) to stop VEYRA.

endlocal
