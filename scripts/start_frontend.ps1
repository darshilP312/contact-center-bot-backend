# ── AI Command Center: Frontend Start Script ──────────────────────────────────
# Run as: powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $ROOT "frontend"

Write-Host "`nStarting AI Command Center Frontend" -ForegroundColor Cyan
Write-Host "   URL: http://localhost:5173" -ForegroundColor Gray

if (-not (Test-Path $frontendDir)) {
    Write-Host "[ERROR] Frontend directory not found: $frontendDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[INFO] node_modules not found. Running npm install..." -ForegroundColor Yellow
    Set-Location $frontendDir
    npm install
}

Write-Host "`nLaunching Vite dev server...`n" -ForegroundColor Green

Set-Location $frontendDir
npm run dev
