@echo off
setlocal EnableDelayedExpansion

title Remis Mod Factory - Emergency Data Reset
color 0E

echo ===============================================================================
echo                           EMERGENCY DATA RESET TOOL
echo ===============================================================================
echo.
echo This tool will DELETE all user data for Remis Mod Factory.
echo.
echo Target Directory: %APPDATA%\RemisModFactory
echo.
echo [WARNING] This includes:
echo  - Local Project Database (remis.sqlite)
echo  - User Settings (config.json)
echo  - Demo Mod Progress
echo  - Cached Translations
echo.
echo Apps installed in "Program Files" will NOT be affected.
echo Use this only if the application fails to start or behaves abnormally.
echo.
echo ===============================================================================
echo.

set /p confirm="Type 'DELETE' to confirm wiping all user data: "

if /i "%confirm%"=="DELETE" (
    echo.
    echo [INFO] Stopping any running instances...
    taskkill /F /IM "remis-mod-factory.exe" >nul 2>&1
    taskkill /F /IM "web_server.exe" >nul 2>&1
    
    echo.
    if exist "%APPDATA%\RemisModFactory" (
        echo [EXEC] Deleting %APPDATA%\RemisModFactory...
        rmdir /s /q "%APPDATA%\RemisModFactory"
        if exist "%APPDATA%\RemisModFactory" (
            color 0C
            echo.
            echo [ERROR] Failed to delete some files. Please ensure the app is closed.
        ) else (
            color 0A
            echo.
            echo [SUCCESS] User data wiped successfully.
            echo You can now restart Remis Mod Factory.
        )
    ) else (
        echo [INFO] Directory not found. Nothing to delete.
    )
) else (
    echo.
    echo [INFO] Operation cancelled. No changes made.
)

echo.
pause
