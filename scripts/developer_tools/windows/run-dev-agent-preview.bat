@echo off
setlocal EnableExtensions

rem INTERVIEW STOPGAP: isolates Agent Preview backend data, WebView identity,
rem and localhost storage origin. Production session storage still needs a
rem separately reviewed migration away from the single localStorage payload.
set "REMIS_BUILD_CHANNEL=agent-preview"
set "VITE_REMIS_BUILD_CHANNEL=agent-preview"
set "REMIS_BACKEND_PORT=1454"
set "REMIS_FRONTEND_PORT=5175"

call "%~dp0run-dev.bat" %*
exit /b %ERRORLEVEL%
