param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$port = if ($env:REMIS_BACKEND_PORT) { [int]$env:REMIS_BACKEND_PORT } else { 1453 }
$url = "http://127.0.0.1:$port/api/health"
try { $health = Invoke-RestMethod -Uri $url -TimeoutSec 2 } catch { $health = $null }
if ($health -and $health.app -eq 'remis' -and
    [IO.Path]::GetFullPath($health.app_root) -eq $root) {
    Write-Output "Remis backend already healthy on $port. No window was opened."
    exit 0
}
if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $port is occupied without a healthy matching Remis backend. Diagnose it before restarting."
}
$env:REMIS_NONINTERACTIVE = '1'
$launcher = Join-Path $root 'scripts\react-ui\run-backend.bat'
Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', ('"{0}"' -f $launcher)) `
    -WorkingDirectory $root -WindowStyle Hidden | Out-Null
$deadline = (Get-Date).AddSeconds(60)
do {
    try {
        $health = Invoke-RestMethod -Uri $url -TimeoutSec 2
        if ($health.app -eq 'remis' -and [IO.Path]::GetFullPath($health.app_root) -eq $root) {
            Write-Output "Remis backend ready on $port. Frontend was not launched."
            exit 0
        }
    } catch {}
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
throw 'Remis backend did not become healthy within 60 seconds.'
