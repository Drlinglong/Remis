@echo off
chcp 65001 >nul
setlocal

set "ENV_NAME=%REMIS_CONDA_ENV%"
if "%ENV_NAME%"=="" set "ENV_NAME=local_factory"
set "PYTHON_SCRIPT=scripts\main.py"

echo ========================================
echo Starting Project Remis...
echo ----------------------------------------

if defined CONDA_EXE (
    echo [INFO] Launching in Conda environment "%ENV_NAME%".
    start "Project Remis" cmd /K call "%CONDA_EXE%" activate "%ENV_NAME%" ^&^& python "%PYTHON_SCRIPT%"
    goto :end
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH, and CONDA_EXE is not available.
    echo [ERROR] Activate your preferred environment first, or set REMIS_CONDA_ENV/CONDA_EXE.
    goto :end
)

echo [INFO] CONDA_EXE not detected. Using the current Python interpreter.
start "Project Remis" cmd /K python "%PYTHON_SCRIPT%"

:end
echo.
pause
