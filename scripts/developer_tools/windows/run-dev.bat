@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..\..") do set "PROJECT_ROOT=%%~fI"
set "BACKEND_LAUNCHER=%PROJECT_ROOT%\scripts\react-ui\run-backend.bat"
set "FRONTEND_LAUNCHER=%PROJECT_ROOT%\scripts\react-ui\run-frontend.bat"

ECHO =================================================================
ECHO == Remis Project - One-Click Development Environment Launcher  ==
ECHO ==                   (Windows Native Mode)                     ==
ECHO =================================================================
ECHO.

if not exist "%BACKEND_LAUNCHER%" (
    ECHO [ERROR] Could not locate the Remis backend launcher.
    ECHO [ERROR] Resolved project root: "%PROJECT_ROOT%"
    pause
    exit /b 1
)

if not exist "%FRONTEND_LAUNCHER%" (
    ECHO [ERROR] Could not locate the Remis frontend launcher.
    ECHO [ERROR] Resolved project root: "%PROJECT_ROOT%"
    pause
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    ECHO [ERROR] Could not enter the Remis project root: "%PROJECT_ROOT%"
    pause
    exit /b 1
)

ECHO Project root: %PROJECT_ROOT%
ECHO.

if "%REMIS_BACKEND_PORT%"=="" set "REMIS_BACKEND_PORT=1453"
for /f "usebackq delims=" %%P in (`python -m scripts.utils.system_utils --select-backend-port %REMIS_BACKEND_PORT%`) do set "REMIS_BACKEND_PORT=%%P"
set "VITE_BACKEND_PORT=%REMIS_BACKEND_PORT%"
ECHO Using backend port %REMIS_BACKEND_PORT%.

if /i "%~1"=="--check" (
    ECHO [OK] Development launcher paths and backend port selection are valid.
    exit /b 0
)

ECHO Launching backend (FastAPI) and frontend (Tauri Desktop) in separate windows...

start "Remis Backend" /D "%PROJECT_ROOT%" "%BACKEND_LAUNCHER%"

ECHO Waiting for backend health check on port %REMIS_BACKEND_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(60); while((Get-Date) -lt $deadline){ try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%REMIS_BACKEND_PORT%/api/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
    ECHO [WARN] Backend did not become healthy within 60 seconds.
    ECHO [WARN] Starting frontend anyway; check the Remis Backend window for errors.
) else (
    ECHO Backend is healthy.
)

start "Remis Frontend" /D "%PROJECT_ROOT%" "%FRONTEND_LAUNCHER%"

ECHO.
ECHO This launcher window will now close.
timeout /t 3 > nul
