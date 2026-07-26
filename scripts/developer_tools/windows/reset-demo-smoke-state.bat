@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..\..") do set "PROJECT_ROOT=%%~fI"

cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo [ERROR] Could not enter repository root: "%PROJECT_ROOT%"
    exit /b 1
)

python scripts\developer_tools\reset_demo_smoke_state.py %*
exit /b %ERRORLEVEL%
