@echo off
REM Wrapper script to run PowerShell pre-commit check
REM Usage: check_before_commit.bat [-Silent]

echo.
echo ===================================
echo   Pre-Commit Quality Check
echo ===================================
echo.

REM Run PowerShell script with arguments
powershell -ExecutionPolicy Bypass -File "%~dp0check_before_commit.ps1" %*
set EXIT_CODE=%errorlevel%

REM If Silent mode is requested, exit immediately with the code
if /i "%1"=="-Silent" exit /b %EXIT_CODE%

REM Pause to see results in interactive mode
pause
exit /b %EXIT_CODE%
