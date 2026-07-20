@echo off
chcp 65001 >nul
setlocal

for %%I in ("%~dp0\..\..\..") do set "PROJECT_ROOT=%%~fI"

pyinstaller --clean --onefile --name web_server ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import pydantic ^
  --collect-submodules pydantic_ai ^
  --collect-submodules pydantic_graph ^
  --collect-data genai_prices ^
  --hidden-import psutil ^
  --hidden-import scripts.hooks ^
  --hidden-import scripts.hooks.file_parser_hook ^
  --hidden-import scripts.config.prompts ^
  --add-data "%PROJECT_ROOT%\data\seed_data_main.sql;data" ^
  --add-data "%PROJECT_ROOT%\data\seed_data_projects.sql;data" ^
  --add-data "%PROJECT_ROOT%\data\lang;data/lang" ^
  --add-data "%PROJECT_ROOT%\docs\zh\user-guides;docs/zh/user-guides" ^
  --add-data "%PROJECT_ROOT%\assets\skeleton.sqlite;assets" ^
  --add-data "%PROJECT_ROOT%\assets\mods_cache_skeleton.sqlite;assets" ^
  "%PROJECT_ROOT%\scripts\web_server.py"
