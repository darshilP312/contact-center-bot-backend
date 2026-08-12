#!/usr/bin/env python3
"""
AI Command Center — Backend Starter (Python alternative)
Usage:
    python scripts/start_backend.py
"""

import sys
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
VENV_DIR = BACKEND_DIR / ".venv"

if sys.platform == "win32":
    venv_python = VENV_DIR / "Scripts" / "python.exe"
else:
    venv_python = VENV_DIR / "bin" / "python"

if not venv_python.exists():
    print(f"[ERROR] Virtual environment not found at {VENV_DIR}.")
    print("Please run setup first: python scripts/setup_env.py")
    sys.exit(1)

print("\nStarting AI Command Center Backend...")
print("  Backend URL: http://localhost:8000")
print("  API Docs:    http://localhost:8000/api/v1/docs\n")

# Run uvicorn
cmd = [str(venv_python), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
subprocess.run(cmd, cwd=str(BACKEND_DIR))
