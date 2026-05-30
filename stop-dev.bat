@echo off
chcp 65001 >nul
setlocal

set "PORTS=%*"
if "%PORTS%"=="" set "PORTS=5173 5174 5175 5176 5177 5178 5179"

echo.
echo [Remis Dev Stop] Closing Remis Tauri development window if it is still running...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$apps = Get-Process -Name remis-mod-factory -ErrorAction SilentlyContinue;" ^
  "if (-not $apps) { Write-Host '[OK] No remis-mod-factory.exe process found.' }" ^
  "foreach ($app in $apps) { Write-Host ('[KILL] remis-mod-factory.exe PID ' + $app.Id); Stop-Process -Id $app.Id -Force }"

echo.
echo [Remis Dev Stop] Checking frontend dev ports: %PORTS%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = '%PORTS%'.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { [int]$_ };" ^
  "foreach ($port in $ports) {" ^
  "  $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue;" ^
  "  if (-not $listeners) { Write-Host ('[OK] Port ' + $port + ' is clear.'); continue }" ^
  "  foreach ($listener in $listeners) {" ^
  "    $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue;" ^
  "    if (-not $proc) { continue }" ^
  "    if ($proc.ProcessName -eq 'node') {" ^
  "      Write-Host ('[KILL] Port ' + $port + ' -> PID ' + $proc.Id + ' node.exe');" ^
  "      Stop-Process -Id $proc.Id -Force" ^
  "    } else {" ^
  "      Write-Host ('[SKIP] Port ' + $port + ' -> PID ' + $proc.Id + ' ' + $proc.ProcessName + '. Not a Vite node process.')" ^
  "    }" ^
  "  }" ^
  "}"

echo.
echo [Remis Dev Stop] Done.
pause
