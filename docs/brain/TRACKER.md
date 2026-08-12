# TRACKER.md — Living Change Log
## Enterprise Voice-First AI Command Center

> **Updated after every meaningful implementation step. A developer can read this document alone and resume work without reading any chat history.**

---

## Current Status

**Phase**: Phase 0 — Brain Files & Project Scaffold (In Progress)
**Active Developer**: AI System Architect (automated build)
**Started**: 2026-08-10

---

## Session Summary

> Read this paragraph to resume work without context:
>
> Building the Enterprise Voice-First AI Command Center from scratch in `c:\Users\2862627\Desktop\command_center_2.0\`. This is a domain-agnostic, voice-first AI platform (demo domain: Insurance). Stack: FastAPI backend, LangGraph orchestrator, faster-whisper STT, Kokoro TTS, Silero VAD, FAISS RAG, Redis sessions, React+TypeScript+Vite frontend. LLM is OpenAI-compatible (Groq/Gemini) via `LLM_BASE_URL`+`LLM_API_KEY`. Embeddings use local sentence-transformers. No Docker, no Azure Speech, PowerShell scripts only. Phase 0 (brain files + scaffold) is in progress. Phases 1-12 are queued.

---

## Completed Items

### 2026-08-10 — Phase 0: Brain Files

| Time | File | Description |
|---|---|---|
| 15:27 | `docs/brain/BRAIN.md` | Architecture decisions log, technology stack, ADL-001 through ADL-010 |
| 15:28 | `docs/brain/RULES.md` | Immutable project rules (coding standards, commit format, logging, domain plugin rules) |
| 15:28 | `docs/brain/TRACKER.md` | This file — living change log |

---

## In Progress

- Phase 0: Remaining scaffold files (`.gitignore`, `.env.example`, `README.md`, API contract, setup docs)
- Phase 1: Backend foundation (FastAPI app, core config, lifespan, API routes)

---

## Upcoming

| Phase | Description |
|---|---|
| Phase 1 | Backend Foundation — FastAPI, config, logging, lifespan, REST endpoints, WebSocket gateway |
| Phase 2 | Data Models — All 9 Pydantic v2 models |
| Phase 3 | Session & Redis Services |
| Phase 4 | Speech Processing Pipeline (STT/TTS/VAD) |
| Phase 5 | Domain Plugin System (Insurance demo domain) |
| Phase 6 | Tool Layer (12 tools, mock implementations) |
| Phase 7 | LangGraph Orchestration Engine (8 nodes + graph) |
| Phase 8 | Policy Engine |
| Phase 9 | Observability (Langfuse + OpenTelemetry, optional) |
| Phase 10 | Tests (unit + integration) |
| Phase 11 | Frontend (React + TypeScript + Vite, 6-panel Command Center UI) |
| Phase 12 | Scripts & Setup Documentation |

---

## Issues & Blockers

| ID | Issue | Status | Resolution |
|---|---|---|---|
| B001 | `kokoro-onnx` package name may vary by pip version | Open | Use `kokoro-onnx` pip name; fallback to `edge-tts` if import fails |
| B002 | Silero VAD requires `torch` which is large (~2GB) | Open | Setup script will use `torch` CPU-only wheel to minimize download |
| B003 | Windows Redis via winget may not be latest version | Open | Document in QUICKSTART.md; Azure Cache for Redis recommended for production |
| B004 | `sentence-transformers` first run downloads model (~80MB) | Open | Auto-download handled by the library; no special setup needed |

---

## Architecture Decisions Made This Session

| ADL ID | Decision |
|---|---|
| ADL-001 | Domain-agnostic platform with YAML plugin architecture |
| ADL-002 | No Docker — Azure Virtual Desktop constraint |
| ADL-003 | Detachable frontend (WebSocket + REST only) |
| ADL-004 | Open-source speech stack (faster-whisper + Kokoro + Silero) |
| ADL-005 | LangGraph for orchestration |
| ADL-006 | FAISS for dev, pgvector for production (via env var toggle) |
| ADL-007 | OpenAI-compatible LLM client (Groq/Gemini endpoint) |
| ADL-008 | Langfuse optional (silently disabled without key) |
| ADL-009 | Local Redis via winget for development |
| ADL-010 | sentence-transformers for local embeddings (all-MiniLM-L6-v2) |
