# ── AI Command Center: Backend Start Script ───────────────────────────────────
# Run as: powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1

param(
    [int]$Port = 8000,
    [string]$LogLevel = "info",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $ROOT "backend\.venv\Scripts\python.exe"
$backendDir = Join-Path $ROOT "backend"

Write-Host "`nStarting AI Command Center Backend" -ForegroundColor Cyan
Write-Host "   Port: $Port | Log Level: $LogLevel" -ForegroundColor Gray

if (-not (Test-Path $venvPython)) {
    Write-Host "[ERROR] Virtual environment not found. Run setup first." -ForegroundColor Red
    exit 1
}

# Load .env
$envFile = Join-Path $ROOT ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([A-Z_]+)=(.*)$" -and $_ -notmatch "^#") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim('"'), "Process")
        }
    }
    Write-Host "  [OK] .env loaded" -ForegroundColor Green
}

$reloadFlag = if ($Reload) { "--reload" } else { "" }

Write-Host "`nLaunching Uvicorn on http://localhost:$Port`n" -ForegroundColor Green

Set-Location $backendDir
& $venvPython -m uvicorn main:app `
    --host 0.0.0.0 `
    --port $Port `
    --log-level $LogLevel `
    $reloadFlag
