@echo off
set "ROOT=%~dp0.."
set "FRONTEND_DIR=%ROOT%\frontend"

echo.
echo Starting AI Command Center Frontend...
echo Frontend URL: http://localhost:5173
echo.

if not exist "%FRONTEND_DIR%\node_modules" (
    echo node_modules not found. Installing dependencies...
    cd /d "%FRONTEND_DIR%"
    call npm install
)

cd /d "%FRONTEND_DIR%"
call npm run dev
