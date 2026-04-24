@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

pyinstaller --clean --onefile --name web_server ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import pydantic ^
  --hidden-import psutil ^
  --hidden-import scripts.hooks ^
  --hidden-import scripts.hooks.file_parser_hook ^
  --hidden-import scripts.config.prompts ^
  --add-data "%PROJECT_ROOT%\data\seed_data_main.sql;data" ^
  --add-data "%PROJECT_ROOT%\data\seed_data_projects.sql;data" ^
  --add-data "%PROJECT_ROOT%\data\lang;data/lang" ^
  --add-data "%PROJECT_ROOT%\assets\skeleton.sqlite;assets" ^
  --add-data "%PROJECT_ROOT%\assets\mods_cache_skeleton.sqlite;assets" ^
  "%PROJECT_ROOT%\scripts\web_server.py"
