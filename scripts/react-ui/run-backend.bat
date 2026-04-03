@echo off
title Remis Backend (FastAPI on Windows)
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"

echo Launching FastAPI backend server...
echo Activating Conda environment 'local_factory'...

call K:\MiniConda\Scripts\activate.bat local_factory
cd /d "%PROJECT_ROOT%"

echo [INFO] Checking for port conflicts...
python -m scripts.utils.system_utils 8081

echo Starting Python server...
python -m uvicorn scripts.web_server:app --host 127.0.0.1 --port 8081 --reload

pause
