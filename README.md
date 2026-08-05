# contact-center-bot-backend

 # Voice AI Agent Backend - Architecture & Onboarding Guide

Welcome to the Voice AI Agent backend repository. We are building the AI layer of a next-generation contact center[cite: 1]. The goal of this MVP is to demonstrate enterprise AI capabilities (streaming voice, agentic workflows, deterministic tools) while keeping the implementation achievable within a 4–8 week timeframe[cite: 1].

This backend is built using **FastAPI** (for high-performance async streaming) and **LangGraph** (for stateful AI orchestration)[cite: 1]. 

## 🏗️ Architectural Philosophy

To prevent this from becoming a tangled monolith, we are using a **Layer-Based Architecture**. We strictly separate the transport layer (WebSockets/WebRTC), the reasoning engine (LangGraph), and the business execution (Mock APIs)[cite: 1].

*   **Speech services handle audio only.**[cite: 1]
*   **The Orchestrator owns state, memory, and workflow progression.**[cite: 1]
*   **Tools perform deterministic actions.**[cite: 1]

## 📂 Folder Structure Breakdown

Our application code lives entirely inside the `app/` directory. Here is where everything goes:

### 1. The Gateway Layer (`app/api/`)
This is the entry point. It contains **no business logic**. It only handles incoming connections and routes data to the services.
*   `routes/websocket.py` & `webrtc_signaling.py`: Handles the real-time audio socket connections.
*   `routes/mock_enterprise.py`: The mock REST endpoints that our AI will "call" to perform actions (like CRM lookups or ticketing).

### 2. The Cognitive Engine / "The Brain" (`app/agents/`)
This is where LangGraph lives. It is responsible for reasoning, state management, and deciding what to do next.
*   `graph.py`: The LangGraph state machine definition.
*   `nodes/`: Individual logic steps (e.g., `intent_router.py`, `tool_caller.py`).
*   `state.py`: TypedDicts defining what variables exist in our working memory.

### 3. The Services Layer (`app/services/`)
This handles external integrations and async coordination.
*   `conversation_service.py`: The traffic cop. It sits between the WebSocket and the AI, managing the voice loop (Audio -> STT -> Agent -> TTS).
*   `audio/`: Azure STT/TTS stream clients and the `stream_manager.py` (which handles user interruptions/barge-in).
*   `memory/`: Redis checkpointer for LangGraph state persistence.

### 4. The Tool & Policy Layer (`app/tools/` & `app/policy/`)
*   `tools/implementations/`: The Python scripts for our specific enterprise actions (e.g., `support.py` for `check_outage()`).
*   `policy/guardrails.py`: Deterministic rules that run *before* a tool executes (e.g., checking if a refund exceeds a maximum limit). Keeps the LLM from inventing business rules[cite: 1].

### 5. Data Contracts (`app/schemas/`)
Pydantic models defining the inputs and outputs across the system. 

---

## 🚀 Getting Started

1. Copy `.env.example` to `.env` and fill in your API keys (Azure, OpenAI).
2. Run `docker-compose up -d` to start Redis and PostgreSQL.
3. Define the shared Pydantic models in `app/schemas/`.
