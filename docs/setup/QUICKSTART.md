# QUICKSTART.md — Windows Native Setup Guide
## Enterprise Voice-First AI Command Center

> **Platform**: Windows 10/11 / Azure Virtual Desktop
> **No Docker Required** — everything runs natively.

---

## Prerequisites

Before running the setup script, ensure you have:

1. **Windows 10 22H2+ or Windows 11** (AVD compatible)
2. **Python 3.11+** — Download from https://python.org or `winget install Python.Python.3.11`
3. **Node.js 20 LTS** — Download from https://nodejs.org or `winget install OpenJS.NodeJS.LTS`
4. **Git** — `winget install Git.Git`
5. **winget** — Comes pre-installed on Windows 11; for Windows 10, update the App Installer from Microsoft Store

---

## Step 1: Clone the Repository

```powershell
git clone <repository-url> command_center_2.0
cd command_center_2.0
```

---

## Step 2: Configure Environment Variables

Copy the example env file and fill in your values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required values to set:
```env
# LLM Configuration (Groq example)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_your_groq_key_here
LLM_MODEL=llama3-70b-8192

# OR Gemini OpenAI-compatible
# LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
# LLM_API_KEY=AIza_your_gemini_key_here
# LLM_MODEL=gemini-2.0-flash
```

---

Open **Command Prompt (cmd.exe)** or terminal and choose one of the following non-PowerShell options:

### Option A: CMD Batch Files (Recommended for AVD)
```cmd
scripts\setup_env.bat
```

### Option B: Python Setup Runner
```cmd
python scripts/setup_env.py
```

### Option C: PowerShell (if permitted)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_env.ps1
```

The setup script will:
1. Install Redis via `winget` (if not already installed)
2. Start Redis as a background service
3. Create a Python virtual environment at `backend/.venv`
4. Install all Python dependencies from `backend/requirements.txt`
5. Download the Kokoro TTS ONNX model weights (~300MB, one-time)
6. Download `sentence-transformers` `all-MiniLM-L6-v2` model (~80MB, one-time)
7. Download `faster-whisper` base model (~150MB, one-time)
8. Install Node.js dependencies in `frontend/`
9. Validate all required environment variables
10. Run a quick health check

**Expected duration**: 5–15 minutes on first run (model downloads).

---

## Step 4: Start the Backend

**CMD / Batch**:
```cmd
scripts\start_backend.bat
```
or **Python**:
```cmd
python scripts/start_backend.py
```
or **PowerShell**:
```powershell
.\scripts\start_backend.ps1
```

Backend will start at: `http://localhost:8000`
- API docs: `http://localhost:8000/api/v1/docs`
- Health check: `http://localhost:8000/api/v1/health`

---

## Step 5: Start the Frontend

In a new terminal window:

**CMD / Batch**:
```cmd
scripts\start_frontend.bat
```
or **Direct npm**:
```cmd
cd frontend
npm run dev
```

Frontend will start at: `http://localhost:5173`

---

## Verification

After both servers are running:

1. Open `http://localhost:5173` in your browser
2. The Command Center UI should load with all 6 panels
3. Click "New Session" — the status bar should show a green dot
4. Type a message: "I want to file a claim for my car accident"
5. You should see: intent detected (`file_claim`), workflow started (`claim_filing`), agent response

---

## Service Dependencies

| Service | Default Port | Setup Method |
|---|---|---|
| FastAPI Backend | 8000 | `start_backend.ps1` |
| Vite Frontend | 5173 | `start_frontend.ps1` |
| Redis | 6379 | `winget install Redis.Redis` (via setup script) |

---

## Troubleshooting

### Redis won't start
```powershell
# Start Redis manually
redis-server --daemonize yes
# Or check Windows services
Get-Service -Name "Redis"
Start-Service -Name "Redis"
```

### Python venv activation fails
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
cd backend
.\.venv\Scripts\Activate.ps1
```

### Kokoro TTS model not found
The setup script downloads Kokoro models to `backend/.models/kokoro/`. If download failed:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from kokoro_onnx import Kokoro; Kokoro.download_model()"
```
If Kokoro fails, set `TTS_PROVIDER=edge_tts` in `.env` to use the free fallback.

### STT model download fails
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### LLM API errors
- Verify `LLM_BASE_URL` and `LLM_API_KEY` in `.env`
- Test with: `curl -H "Authorization: Bearer $env:LLM_API_KEY" "$env:LLM_BASE_URL/models"`
- For Groq: https://console.groq.com/keys
- For Gemini: https://aistudio.google.com/apikey

### Port conflicts
Change ports in `.env`:
```env
BACKEND_PORT=8001
FRONTEND_PORT=5174
```

---

## Production Deployment Notes

For production on Azure Virtual Desktop:

1. **Redis**: Replace local Redis with **Azure Cache for Redis**. Set `REDIS_URL` in `.env`.
2. **Vector Store**: Replace FAISS with **PostgreSQL + pgvector**. Set `VECTOR_STORE=pgvector` and `POSTGRES_URL` in `.env`.
3. **LLM**: Consider **Azure OpenAI** for data residency compliance.
4. **Secrets**: Inject env vars from **Azure Key Vault** — do NOT use `.env` files in production.
5. **STT/TTS Models**: Store pre-downloaded models in a shared Azure Files mount to avoid re-downloading across sessions.
6. **Process management**: Use Windows Task Scheduler or NSSM (Non-Sucking Service Manager) to manage the FastAPI process as a Windows service.
