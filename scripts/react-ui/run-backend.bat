@echo off
title Remis Backend (FastAPI on Windows)
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"
set "ENV_NAME=%REMIS_CONDA_ENV%"
if "%ENV_NAME%"=="" set "ENV_NAME=local_factory"

echo Launching FastAPI backend server...
cd /d "%PROJECT_ROOT%"

if defined CONDA_EXE (
    echo Activating Conda environment "%ENV_NAME%"...
    call "%CONDA_EXE%" activate "%ENV_NAME%"
    if errorlevel 1 (
        echo [ERROR] Failed to activate Conda environment "%ENV_NAME%".
        pause
        exit /b 1
    )
) else (
    echo [INFO] CONDA_EXE not detected. Using the current Python interpreter.
)

echo [INFO] Checking for port conflicts...
python -m scripts.utils.system_utils 8081

echo Starting Python server...
python -m uvicorn scripts.web_server:app --host 127.0.0.1 --port 8081 --reload

pause
