@echo off
setlocal

for %%I in ("%~dp0\..\..\..") do set "PROJECT_ROOT=%%~fI"
pushd "%PROJECT_ROOT%"

REM Build the packaged Project Remis desktop release.
python scripts\build_pipeline.py
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
