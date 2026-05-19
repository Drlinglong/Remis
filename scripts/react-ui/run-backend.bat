@echo off
title Remis Backend (FastAPI on Windows)
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"
set "ENV_NAME=%REMIS_CONDA_ENV%"
if "%ENV_NAME%"=="" set "ENV_NAME=local_factory"

echo Launching FastAPI backend server...
cd /d "%PROJECT_ROOT%"

set "PYTHON_EXE=python"
set "CONDA_BASE="

if defined REMIS_PYTHON_EXE if exist "%REMIS_PYTHON_EXE%" set "PYTHON_EXE=%REMIS_PYTHON_EXE%"

if "%PYTHON_EXE%"=="python" if defined REMIS_CONDA_BASE if exist "%REMIS_CONDA_BASE%\envs\%ENV_NAME%\python.exe" set "PYTHON_EXE=%REMIS_CONDA_BASE%\envs\%ENV_NAME%\python.exe"

if "%PYTHON_EXE%"=="python" if defined CONDA_EXE (
    for /f "usebackq delims=" %%B in (`"%CONDA_EXE%" info --base`) do set "CONDA_BASE=%%B"
    if exist "!CONDA_BASE!\envs\%ENV_NAME%\python.exe" set "PYTHON_EXE=!CONDA_BASE!\envs\%ENV_NAME%\python.exe"
)

if "%PYTHON_EXE%"=="python" if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\envs\%ENV_NAME%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\envs\%ENV_NAME%\python.exe"
if "%PYTHON_EXE%"=="python" if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\..\%ENV_NAME%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\..\%ENV_NAME%\python.exe"

if "%PYTHON_EXE%"=="python" (
    for %%D in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "K:\MiniConda" "C:\ProgramData\miniconda3" "C:\ProgramData\anaconda3") do (
        if "!PYTHON_EXE!"=="python" if exist "%%~fD\envs\%ENV_NAME%\python.exe" set "PYTHON_EXE=%%~fD\envs\%ENV_NAME%\python.exe"
    )
)

if not "%PYTHON_EXE%"=="python" (
    echo [INFO] Using Conda environment Python: "%PYTHON_EXE%"
) else (
    echo [INFO] Conda environment "%ENV_NAME%" was not detected. Using the current Python interpreter.
)

echo [INFO] Checking for port conflicts...
if "%REMIS_BACKEND_PORT%"=="" set "REMIS_BACKEND_PORT=1453"
"%PYTHON_EXE%" -m scripts.utils.system_utils %REMIS_BACKEND_PORT%

echo Starting Python server...
"%PYTHON_EXE%" -m uvicorn scripts.web_server:app --host 127.0.0.1 --port %REMIS_BACKEND_PORT% --reload
if errorlevel 1 (
    echo [ERROR] Backend server exited with code %ERRORLEVEL%.
)

pause
