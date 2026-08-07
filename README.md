# AI Contact Centre — Enterprise AI Layer

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # Fill in your keys
python -m app.rag.indexer    # Build FAISS index
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev
```

## Architecture

See `.agents/brain.md` for full architectural documentation.

## Rules

See `.agents/instructions.md` for immutable project rules.

## Change Log

See `.agents/summary.md` for the complete change tracker.

## Workflows

- **Technical Support**: Internet issue → diagnostics → engineer booking → ticket
- **Billing & Refund**: Invoice → eligibility → refund → confirmation
- **Policy RAG**: Knowledge questions answered from documents with citations

## API Docs

After starting backend: http://localhost:8000/docs

## Team

- **A** — AI Orchestrator Lead (LangGraph, state, intent, policy, voice integration)
- **B** — Backend Lead (tools, workflows, RAG, observability)
- **C** — Frontend Lead (AudioClient, UI components, WebSocket)
