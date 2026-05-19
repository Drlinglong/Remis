@echo off
ECHO =================================================================
ECHO == Remis Project - One-Click Development Environment Launcher  ==
ECHO ==                   (Windows Native Mode)                     ==
ECHO =================================================================
ECHO.

ECHO Launching backend (FastAPI) and frontend (Tauri Desktop) in separate windows...

if "%REMIS_BACKEND_PORT%"=="" set "REMIS_BACKEND_PORT=1453"

start "Remis Backend" scripts\react-ui\run-backend.bat

ECHO Waiting for backend health check on port %REMIS_BACKEND_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(60); while((Get-Date) -lt $deadline){ try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%REMIS_BACKEND_PORT%/api/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
    ECHO [WARN] Backend did not become healthy within 60 seconds.
    ECHO [WARN] Starting frontend anyway; check the Remis Backend window for errors.
) else (
    ECHO Backend is healthy.
)

start "Remis Frontend" scripts\react-ui\run-frontend.bat

ECHO.
ECHO This launcher window will now close.
timeout /t 3 > nul
