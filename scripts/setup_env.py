#!/usr/bin/env python3
"""
AI Command Center — Environment Setup Script (Python alternative)
Runs on Windows CMD, Git Bash, or PowerShell without execution policy or encoding restrictions.
Usage:
    python scripts/setup_env.py
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
VENV_DIR = BACKEND_DIR / ".venv"

def print_step(title):
    print(f"\n[STEP] {title}")

def check_command(cmd, name):
    if shutil.which(cmd) is None:
        print(f"  [ERROR] {name} not found. Please install it first.")
        return False
    print(f"  [OK] {name} found")
    return True

def main():
    print("\n============================================================")
    print(" AI Command Center -- Python Setup Script")
    print("============================================================")

    # 1. Check prerequisites
    print_step("1/5 Checking prerequisites...")
    ok = True
    ok = check_command("python", "Python 3.11+") and ok
    ok = check_command("node", "Node.js 18+") and ok
    ok = check_command("npm", "npm") and ok

    if not ok:
        print("\n[ERROR] Missing prerequisites. Please install required dependencies.")
        sys.exit(1)

    # 2. Virtual environment
    print_step("2/5 Setting up Python virtual environment...")
    if not VENV_DIR.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        print(f"  [OK] Virtual environment created at: {VENV_DIR}")
    else:
        print(f"  [INFO] Virtual environment already exists at: {VENV_DIR}")

    # Determine venv executables
    if sys.platform == "win32":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
        venv_pip = VENV_DIR / "Scripts" / "pip.exe"
    else:
        venv_python = VENV_DIR / "bin" / "python"
        venv_pip = VENV_DIR / "bin" / "pip"

    # 3. Install backend dependencies
    print_step("3/5 Installing backend dependencies (this may take a few minutes)...")
    req_file = BACKEND_DIR / "requirements.txt"
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=True)
    res = subprocess.run([str(venv_pip), "install", "-r", str(req_file)])
    if res.returncode != 0:
        print("  [ERROR] Failed to install backend dependencies.")
        sys.exit(1)
    print("  [OK] Backend dependencies installed successfully.")

    # 4. Install frontend dependencies
    print_step("4/5 Installing frontend dependencies...")
    if FRONTEND_DIR.exists():
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        res = subprocess.run([npm_cmd, "install"], cwd=str(FRONTEND_DIR))
        if res.returncode == 0:
            print("  [OK] Frontend dependencies installed successfully.")
        else:
            print("  [WARNING] npm install reported warnings or errors.")
    else:
        print(f"  [WARNING] Frontend directory not found at: {FRONTEND_DIR}")

    # 5. Environment file
    print_step("5/5 Checking environment variables...")
    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("  [OK] .env file created from .env.example")
            print("  [ACTION REQUIRED] Edit .env and set your LLM API Key (GROQ_API_KEY / OPENAI_API_KEY).")
    else:
        print("  [INFO] .env file already exists — keeping existing file.")

    print("\n============================================================")
    print(" [OK] Setup complete!")
    print("============================================================")
    print("Next steps:")
    print("  1. Edit .env with your LLM API key")
    print("  2. Start Backend:  python scripts/start_backend.py (or scripts\\start_backend.bat)")
    print("  3. Start Frontend: scripts\\start_frontend.bat (or cd frontend && npm run dev)")
    print("============================================================\n")

if __name__ == "__main__":
    main()
