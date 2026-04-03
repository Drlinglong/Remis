@echo off
title Remis Frontend (Tauri Desktop Dev)
setlocal

set "FRONTEND_DIR=%~dp0"

echo Launching Tauri desktop development shell...
cd /d "%FRONTEND_DIR%"

if not exist "node_modules" (
    echo [INFO] Frontend dependencies not found. Installing with npm ci...
    call npm ci
    if errorlevel 1 (
        echo [ERROR] npm ci failed. Frontend dependencies were not installed.
        pause
        exit /b 1
    )
)

echo Starting Tauri desktop dev...
call npm run tauri:desktop-dev

pause
