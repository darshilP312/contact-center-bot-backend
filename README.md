# Enterprise Voice-First AI Command Center

> A production-grade, domain-agnostic **Enterprise Voice-First AI Command Center** — a real-time, multi-modal (Voice + Text) AI agent platform for enterprise contact centers.

---

## What Is This?

A single, domain-agnostic AI engine that can be configured to serve any business vertical (Insurance, Telecom, Banking, E-commerce, Healthcare) by swapping only the domain configuration plugin. **No core code changes required to add a new domain.**

**Demo Domain**: Insurance — three complete scenarios: Claim Filing, Policy Inquiry, Renewal Support.

---

## Architecture

```
Browser (WebRTC/Chat)
        │
        ▼
FastAPI WebSocket Gateway
        │
        ├── STT Pipeline (faster-whisper + Silero VAD)
        │
        ├── LangGraph Orchestrator
        │       ├── conversation_understanding
        │       ├── planner
        │       ├── guardrails
        │       ├── business_router
        │       ├── rag (FAISS)
        │       ├── tool_caller
        │       ├── workflow_executor
        │       ├── response_generator
        │       └── escalation_handler
        │
        └── TTS Pipeline (Kokoro ONNX / edge-tts fallback)

Domain Plugin (Insurance)          Redis (Session State)
├── domain.yaml (intents)          FAISS (RAG embeddings)
├── workflows/*.yaml               sentence-transformers
├── policies/rules.yaml            Langfuse (optional traces)
└── knowledge/*.md
```

---

## Quick Start

```cmd
# OPTION A: Windows Command Prompt (CMD) / Batch Files (Recommended for AVD)
scripts\setup_env.bat
scripts\start_backend.bat
scripts\start_frontend.bat

# OPTION B: Python Runners
python scripts/setup_env.py
python scripts/start_backend.py
cd frontend && npm run dev

# OPTION C: PowerShell
.\scripts\setup_env.ps1
.\scripts\start_backend.ps1
.\scripts\start_frontend.ps1
```

Open `http://localhost:5173` → Command Center is ready.

Full setup guide: [docs/setup/QUICKSTART.md](docs/setup/QUICKSTART.md)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Orchestration | LangGraph |
| LLM | OpenAI-compatible (Groq / Gemini / Azure OpenAI) |
| STT | faster-whisper (CTranslate2) |
| VAD | Silero VAD |
| TTS | Kokoro ONNX (primary) / edge-tts (fallback) |
| Session State | Redis (local or Azure Cache) |
| Vector Store | FAISS (dev) / pgvector (production) |
| Embeddings | sentence-transformers (local, no API key) |
| Observability | Langfuse + OpenTelemetry (optional) |
| Frontend | React 18 + TypeScript + Vite + Zustand |

---

## Project Structure

```
/
├── frontend/          # Detachable mock React UI
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/           # REST + WebSocket endpoints
│   │   ├── core/          # Config, logging, lifespan
│   │   ├── models/        # Pydantic data models
│   │   ├── services/      # STT, TTS, LLM, Session services
│   │   ├── orchestrator/  # LangGraph engine
│   │   ├── domains/       # Domain plugins (YAML)
│   │   ├── tools/         # Tool implementations
│   │   └── policies/      # Policy engine
│   └── tests/
├── docs/
│   ├── brain/         # BRAIN.md, RULES.md, TRACKER.md
│   ├── api/           # API_CONTRACT.md
│   └── setup/         # QUICKSTART.md, DOMAIN_GUIDE.md
├── scripts/           # PowerShell setup + start scripts
├── .env.example       # Environment template (never commit .env)
└── README.md
```

---

## Key Rules

- **No Docker** — runs natively on Windows / Azure Virtual Desktop
- **Domain-agnostic core** — zero hardcoded domain knowledge in orchestrator
- **Detachable frontend** — backend works without frontend
- **All scripts are PowerShell** — no bash/shell

---

## Adding a New Domain

See [docs/setup/DOMAIN_GUIDE.md](docs/setup/DOMAIN_GUIDE.md). In summary:
1. Create `backend/app/domains/<domain_name>/domain.yaml`
2. Add workflows, policies, knowledge documents
3. Optionally add domain-specific Python tools
4. Restart backend — domain is auto-discovered

**No changes to existing Python files required.**

---

## Documentation

| Document | Description |
|---|---|
| [BRAIN.md](docs/brain/BRAIN.md) | Architecture decisions, technology stack, ADL |
| [RULES.md](docs/brain/RULES.md) | Immutable coding standards and project rules |
| [TRACKER.md](docs/brain/TRACKER.md) | Living change log (resume development from here) |
| [API_CONTRACT.md](docs/api/API_CONTRACT.md) | WebSocket + REST API contract |
| [QUICKSTART.md](docs/setup/QUICKSTART.md) | End-to-end Windows setup guide |
| [DOMAIN_GUIDE.md](docs/setup/DOMAIN_GUIDE.md) | Adding new domain plugins |

---

## License

Internal use — Enterprise AI Platform. All mock tool implementations must be replaced with real API integrations before production deployment.
