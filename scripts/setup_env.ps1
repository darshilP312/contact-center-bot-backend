# ── AI Command Center: Environment Setup Script ─────────────────────────────
# Run as: powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "`nAI Command Center -- Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor DarkGray

# ── Helper functions ──────────────────────────────────────────────────────────
function Check-Command($cmd, $friendly) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  [ERROR] $friendly not found. Please install it first." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] $friendly found" -ForegroundColor Green
}

function Step($msg) {
    Write-Host "`n[STEP] $msg" -ForegroundColor Yellow
}

# ── Step 1: Check prerequisites ───────────────────────────────────────────────
Step "Checking prerequisites..."

Check-Command "python" "Python 3.11+"
Check-Command "node" "Node.js 18+"
Check-Command "npm" "npm"

$pyVersion = python --version 2>&1
Write-Host "  Python: $pyVersion" -ForegroundColor Gray

$nodeVersion = node --version 2>&1
Write-Host "  Node: $nodeVersion" -ForegroundColor Gray

if (-not (Get-Command "redis-server" -ErrorAction SilentlyContinue)) {
    Write-Host "  [WARNING] Redis not found. Install with: winget install Redis.Redis" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Redis found" -ForegroundColor Green
}

# ── Step 2: Python virtual environment ───────────────────────────────────────
Step "Setting up Python virtual environment..."

$venvPath = Join-Path $ROOT "backend\.venv"
if ((-not (Test-Path $venvPath)) -or $Force) {
    python -m venv $venvPath
    Write-Host "  [OK] Virtual environment created at: $venvPath" -ForegroundColor Green
} else {
    Write-Host "  [INFO] Virtual environment already exists (use -Force to recreate)" -ForegroundColor Gray
}

$pip = Join-Path $venvPath "Scripts\pip.exe"
$python = Join-Path $venvPath "Scripts\python.exe"

# ── Step 3: Install backend dependencies ─────────────────────────────────────
Step "Installing backend dependencies (this may take a few minutes)..."

& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $ROOT "backend\requirements.txt") 2>&1 | ForEach-Object {
    if ($_ -match "Successfully installed") { Write-Host "  [OK] $_" -ForegroundColor Green }
    elseif ($_ -match "error" -or $_ -match "Error") { Write-Host "  [ERROR] $_" -ForegroundColor Red }
}
Write-Host "  [OK] Backend dependencies installed" -ForegroundColor Green

# ── Step 4: Install frontend dependencies ────────────────────────────────────
Step "Installing frontend dependencies..."

$frontendPath = Join-Path $ROOT "frontend"
if (Test-Path $frontendPath) {
    Push-Location $frontendPath
    npm install --silent
    Pop-Location
    Write-Host "  [OK] Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  [WARNING] Frontend directory not found at: $frontendPath" -ForegroundColor Yellow
}

# ── Step 5: .env file ────────────────────────────────────────────────────────
Step "Setting up environment variables..."

$envFile = Join-Path $ROOT ".env"
$envExample = Join-Path $ROOT ".env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "  [OK] .env created from .env.example" -ForegroundColor Green
        Write-Host "  [ACTION REQUIRED] Edit .env and add your LLM API key" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [INFO] .env already exists -- not overwriting" -ForegroundColor Gray
}

Write-Host "`n[OK] Setup complete!" -ForegroundColor Green
