@echo off
set "ROOT=%~dp0.."
set "VENV_PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
set "BACKEND_DIR=%ROOT%\backend"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found at backend\.venv.
    echo Please run scripts\setup_env.bat first.
    pause
    exit /b 1
)

echo.
echo Starting AI Command Center Backend...
echo Backend URL: http://localhost:8000
echo API Docs:    http://localhost:8000/api/v1/docs
echo.

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
