@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo  AI Command Center -- Environment Setup (CMD Batch)
echo ============================================================

set "ROOT=%~dp0.."

:: Step 1: Check prerequisites
echo.
echo [1/5] Checking prerequisites...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+ and add it to PATH.
    pause
    exit /b 1
)
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 20+ and add it to PATH.
    pause
    exit /b 1
)
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm not found. Please install Node.js and add it to PATH.
    pause
    exit /b 1
)
echo [OK] Python, Node, and npm found.

:: Step 2: Python Virtual Environment
echo.
echo [2/5] Setting up Python virtual environment...
if not exist "%ROOT%\backend\.venv" (
    python -m venv "%ROOT%\backend\.venv"
    echo [OK] Virtual environment created at backend\.venv
) else (
    echo [INFO] Virtual environment already exists at backend\.venv
)

:: Step 3: Install Backend Dependencies
echo.
echo [3/5] Installing backend dependencies (this may take a few minutes)...
"%ROOT%\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%ROOT%\backend\.venv\Scripts\pip.exe" install -r "%ROOT%\backend\requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)
echo [OK] Backend dependencies installed successfully.

:: Step 4: Install Frontend Dependencies
echo.
echo [4/5] Installing frontend dependencies...
if exist "%ROOT%\frontend" (
    cd /d "%ROOT%\frontend"
    call npm install
    cd /d "%ROOT%"
    echo [OK] Frontend dependencies installed successfully.
) else (
    echo [WARNING] Frontend directory not found.
)

:: Step 5: Copy .env file if missing
echo.
echo [5/5] Checking .env configuration...
if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo [OK] .env file created from .env.example
        echo [ACTION REQUIRED] Edit .env and set your LLM API Key (GROQ_API_KEY / OPENAI_API_KEY).
    )
) else (
    echo [INFO] .env file already exists.
)

echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo Next steps:
echo   1. Edit .env with your LLM API key
echo   2. Start Backend:  scripts\start_backend.bat
echo   3. Start Frontend: scripts\start_frontend.bat
echo   4. Open browser:   http://localhost:5173
echo ============================================================
