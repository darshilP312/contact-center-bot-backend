# 🏗️ Flagship Enterprise AI Contact Center Layer
## Master Implementation Blueprint & Codebase Guide

> **Principle:** LLMs plan and speak. Deterministic code executes and guards.

---

## Table of Contents

1. [Section 1 — Master Folder Structure & Setup Guide](#section-1)
2. [Section 2 — Complete Data Schemas & Contracts](#section-2)
3. [Section 3 — Core LangGraph Orchestrator Loop](#section-3)
4. [Section 4 — Policy Engine & Enterprise Mock Tools](#section-4)
5. [Section 5 — React + TypeScript UI Components](#section-5)
6. [Section 6 — Phased Week-by-Week Implementation Plan](#section-6)
7. [Section 7 — Demo Execution Checklist & Test Cases](#section-7)

---

## Section 1 — Master Folder Structure & Setup Guide {#section-1}

### Repository Layout

```
contact-centre-demo/
├── docker-compose.yml              # Redis + PostgreSQL + pgAdmin
├── .env.example                    # API key templates (never commit real keys)
├── Makefile                        # dev shortcuts
├── README.md
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py                 # FastAPI app + WebSocket gateway
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   │
│   │   ├── state.py                # ConversationState schema (Pydantic)
│   │   ├── telemetry.py            # OpenTelemetry + Langfuse structured logging
│   │   │
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py            # LangGraph StateGraph definition
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── understand.py   # Node 1: Intent + entity extraction
│   │   │   │   ├── router.py       # Node 2: Multi-intent decomposition
│   │   │   │   ├── plan.py         # Node 3: Action planning (tool|rag|ask|escalate)
│   │   │   │   ├── policy.py       # Node 4: Deterministic policy guard
│   │   │   │   ├── execute.py      # Node 5: Tool dispatch + RAG retrieval
│   │   │   │   └── respond.py      # Node 6: Response generation + TTS stream
│   │   │   └── prompts.py          # All LLM prompt templates
│   │   │
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── contracts.py        # ToolResult TypedDict
│   │   │   ├── lookup_customer.py
│   │   │   ├── check_outage.py
│   │   │   ├── run_diagnostics.py
│   │   │   ├── book_engineer.py
│   │   │   ├── refund_payment.py
│   │   │   ├── create_ticket.py
│   │   │   └── router.py           # FastAPI sub-app mounting all tools
│   │   │
│   │   ├── workflows/
│   │   │   ├── loader.py           # YAML→WorkflowDefinition parser
│   │   │   ├── executor.py         # Step tracker, transition resolver
│   │   │   ├── technical_support.yaml
│   │   │   ├── billing_refund.yaml
│   │   │   └── policy_rag.yaml
│   │   │
│   │   ├── policies/
│   │   │   ├── __init__.py
│   │   │   └── engine.py           # Deterministic rule evaluator
│   │   │
│   │   └── rag/
│   │       ├── __init__.py
│   │       ├── indexer.py          # Embed + store policy docs into FAISS
│   │       ├── retriever.py        # Similarity search + citation builder
│   │       └── corpus/
│   │           ├── cancellation_policy.txt
│   │           ├── refund_policy.txt
│   │           └── warranty_policy.txt
│   │
│   └── tests/
│       ├── test_state.py
│       ├── test_tools.py           # Contract tests (ToolResult shape)
│       ├── test_orchestrator.py    # Text-in / state-out orchestrator tests
│       ├── test_policy.py          # Large refund held, angry escalation
│       ├── test_rag_routing.py     # Knowledge → RAG, action → tool
│       └── test_workflows.py       # Step transitions
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        │
        ├── AudioClient.ts          # Mic capture + WebSocket streamer + playback
        ├── player.ts               # Chunked base64 PCM audio player
        ├── wsTypes.ts              # WebSocket message type definitions
        │
        ├── components/
        │   ├── TranscriptPanel.tsx     # Live speech with RAG citations
        │   ├── WorkflowProgressPanel.tsx  # Real-time step visualizer
        │   ├── ObservabilityPanel.tsx  # Latency / token / cost per turn
        │   └── Header.tsx
        │
        ├── hooks/
        │   ├── useAudioSession.ts
        │   └── useConversationState.ts
        │
        └── store/
            └── conversationStore.ts    # Zustand state store
```

---

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    container_name: cc_redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:15-alpine
    container_name: cc_postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-ccuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ccpass}
      POSTGRES_DB: ${POSTGRES_DB:-contact_centre}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-ccuser}"]
      interval: 5s
      timeout: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4
    container_name: cc_pgadmin
    ports:
      - "5050:80"
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@local.dev
      PGADMIN_DEFAULT_PASSWORD: admin
    depends_on:
      - postgres

volumes:
  redis_data:
  postgres_data:
```

---

### `.env.example`

```env
# LLM
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini          # Confirm tool-calling support before building
UNDERSTAND_MODEL=gpt-4o-mini   # Small/fast model for intent extraction
PLAN_MODEL=gpt-4o              # Stronger model for planning
GENERATE_MODEL=gpt-4o-mini     # Fast model for TTS-ready response

# Speech services
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=eastus
# Alternative: Deepgram
DEEPGRAM_API_KEY=

# Storage
REDIS_URL=redis://localhost:6379
POSTGRES_URL=postgresql://ccuser:ccpass@localhost:5432/contact_centre
POSTGRES_USER=ccuser
POSTGRES_PASSWORD=ccpass
POSTGRES_DB=contact_centre

# Observability
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# App
APP_ENV=development
LOG_LEVEL=DEBUG
```

---

### `Makefile`

```makefile
.PHONY: dev infra test lint

infra:
	docker compose up -d

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v --tb=short

lint:
	cd backend && ruff check app/ && mypy app/
	cd frontend && npx tsc --noEmit

seed-rag:
	cd backend && python -m app.rag.indexer
```

---

## Section 2 — Complete Data Schemas & Contracts {#section-2}

### 2.1 `ConversationState` — `backend/app/state.py`

```python
"""
ConversationState — single source of truth for every session.
Stored in Redis. Read and written by every component.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Sub-models ──────────────────────────────────────────────────────────────

class CustomerInfo(BaseModel):
    verified: bool = False
    customer_id: Optional[str] = None
    name: Optional[str] = None
    tier: Optional[Literal["standard", "premium"]] = None
    phone: Optional[str] = None
    account_no: Optional[str] = None


class IntentInfo(BaseModel):
    name: Optional[str] = None          # "technical_support" | "billing" | ...
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)
    # Compound intent support
    secondary_intents: list[str] = Field(default_factory=list)


class WorkflowState(BaseModel):
    name: Optional[str] = None          # active workflow id
    step: Optional[str] = None          # current step id
    completed_steps: list[str] = Field(default_factory=list)
    step_attempts: dict[str, int] = Field(default_factory=dict)
    step_results: dict[str, Any] = Field(default_factory=dict)


class SessionFlags(BaseModel):
    ticket_created: bool = False
    engineer_booked: bool = False
    escalated: bool = False
    awaiting_approval: bool = False
    refund_triggered: bool = False
    rag_used: bool = False
    barge_in_detected: bool = False


class TranscriptEntry(BaseModel):
    role: Literal["user", "assistant", "system"]
    text: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rag_citations: list[str] = Field(default_factory=list)


class WorkingMemory(BaseModel):
    """Short-lived facts about the current turn."""
    current_workflow: Optional[str] = None
    router_restarted: bool = False
    diagnostics_run: int = 0
    last_tool_result: Optional[dict] = None
    pending_action: Optional[str] = None


class LongTermMemory(BaseModel):
    """Persisted across sessions — load from Postgres on session start."""
    previous_tickets: list[str] = Field(default_factory=list)
    last_call_date: Optional[datetime] = None
    engineer_visit_history: list[str] = Field(default_factory=list)
    known_issues: list[str] = Field(default_factory=list)


class ObservabilityMetrics(BaseModel):
    """Per-turn observability — written by telemetry.py."""
    turn_latencies_ms: list[dict[str, float]] = Field(default_factory=list)
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    tool_calls_made: list[str] = Field(default_factory=list)


# ─── Root State ──────────────────────────────────────────────────────────────

class ConversationState(BaseModel):
    """
    The spine of the system. One object per session.
    Serialised to Redis as JSON.  Every component reads and writes this.
    """

    # Identity
    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channel: Literal["voice", "text", "web"] = "voice"

    # Core state
    customer: CustomerInfo = Field(default_factory=CustomerInfo)
    intent: IntentInfo = Field(default_factory=IntentInfo)
    workflow: WorkflowState = Field(default_factory=WorkflowState)
    flags: SessionFlags = Field(default_factory=SessionFlags)

    # Sentiment
    sentiment: Literal["neutral", "frustrated", "angry", "satisfied"] = "neutral"

    # Turn counter
    turn_count: int = 0

    # Memory layers
    working_memory: WorkingMemory = Field(default_factory=WorkingMemory)
    long_term_memory: LongTermMemory = Field(default_factory=LongTermMemory)

    # Transcript history (conversation memory)
    transcript: list[TranscriptEntry] = Field(default_factory=list)

    # Observability
    metrics: ObservabilityMetrics = Field(default_factory=ObservabilityMetrics)

    # Handoff summary (generated on escalation)
    handoff_summary: Optional[str] = None

    class Config:
        use_enum_values = True

    def to_redis(self) -> str:
        """Serialise for Redis storage."""
        return self.model_dump_json()

    @classmethod
    def from_redis(cls, raw: str) -> "ConversationState":
        """Deserialise from Redis."""
        return cls.model_validate_json(raw)

    def add_transcript(self, role: str, text: str, citations: list[str] = None) -> None:
        self.transcript.append(TranscriptEntry(
            role=role,
            text=text,
            rag_citations=citations or []
        ))

    def advance_workflow_step(self, next_step: str, result: dict = None) -> None:
        if self.workflow.step:
            self.workflow.completed_steps.append(self.workflow.step)
        if result:
            self.workflow.step_results[self.workflow.step or ""] = result
        self.workflow.step = next_step

    def increment_step_attempt(self) -> int:
        step = self.workflow.step or "__unknown__"
        self.workflow.step_attempts[step] = self.workflow.step_attempts.get(step, 0) + 1
        return self.workflow.step_attempts[step]
```

---

### 2.2 `ToolResult` Contract — `backend/app/tools/contracts.py`

```python
"""
Uniform return type for every enterprise tool.
Every tool MUST return a ToolResult — never a bare value, never a raised
exception the LLM has to interpret.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class ToolResult(TypedDict):
    ok: bool
    data: dict[str, Any]      # populated when ok=True
    error: Optional[str]       # populated when ok=False


class ToolDefinition(TypedDict):
    """Schema shown to the LLM for tool selection."""
    name: str
    description: str
    input_schema: dict[str, Any]


def ok_result(data: dict) -> ToolResult:
    """Convenience constructor for a successful result."""
    return {"ok": True, "data": data, "error": None}


def err_result(error: str) -> ToolResult:
    """Convenience constructor for a failed result."""
    return {"ok": False, "data": {}, "error": error}
```

---

### 2.3 YAML Workflow Schemas

#### `backend/app/workflows/technical_support.yaml`

```yaml
name: technical_support
description: Diagnose and resolve a connectivity or technical problem.
entry_step: authenticate

steps:
  authenticate:
    goal: Verify the caller identity using their account number or phone.
    tool: lookup_customer
    on_success: check_outage
    on_fail: escalate
    max_attempts: 2

  check_outage:
    goal: Rule out a known network outage in the customer's area.
    tool: check_outage
    on_success: run_diagnostics
    branch:
      outage_found: create_ticket_outage

  create_ticket_outage:
    goal: Log the outage-related incident and inform the customer.
    tool: create_ticket
    on_success: confirm
    metadata:
      ticket_type: outage
      auto_resolve_eta: true

  run_diagnostics:
    goal: Attempt automated remote diagnostic checks and fixes.
    tool: run_diagnostics
    max_attempts: 3
    on_success: create_ticket
    on_exhausted: book_engineer   # policy: 3 diagnostic failures → engineer visit

  book_engineer:
    goal: Schedule a field technician visit.
    tool: book_engineer
    on_success: create_ticket
    on_fail: escalate

  create_ticket:
    goal: Record the interaction in the ticketing system.
    tool: create_ticket
    on_success: confirm

  escalate:
    goal: Transfer to a live human agent with a full handoff summary.
    tool: human_escalation
    terminal: true

  confirm:
    goal: Summarise the outcome and next steps to the customer.
    terminal: true
    generate_summary: true
```

#### `backend/app/workflows/billing_refund.yaml`

```yaml
name: billing_refund
description: Handle billing disputes, payment issues, and refund requests.
entry_step: authenticate

steps:
  authenticate:
    goal: Verify the caller identity.
    tool: lookup_customer
    on_success: lookup_invoice
    on_fail: escalate
    max_attempts: 2

  lookup_invoice:
    goal: Retrieve the disputed invoice or payment record.
    tool: lookup_invoice
    on_success: verify_refund_eligibility
    on_fail: escalate

  verify_refund_eligibility:
    goal: Check if the amount and circumstance qualifies for a refund.
    tool: check_refund_eligibility
    on_success: refund_payment
    branch:
      ineligible: explain_policy   # route to RAG for policy explanation

  explain_policy:
    goal: Explain refund/billing policy from the knowledge base.
    action: rag
    rag_query_template: "refund policy for {reason}"
    terminal: true

  refund_payment:
    goal: Process the refund. Amounts > 10000 require manager approval (policy gate).
    tool: refund_payment
    on_success: send_confirmation
    on_fail: escalate
    policy_gated: true            # triggers policy engine check before execution

  send_confirmation:
    goal: Notify the customer via SMS/email and log the refund.
    tool: send_sms
    on_success: create_ticket

  create_ticket:
    goal: Record the refund transaction.
    tool: create_ticket
    on_success: confirm

  escalate:
    goal: Transfer to a live agent.
    tool: human_escalation
    terminal: true

  confirm:
    goal: Confirm refund timeline and close the interaction.
    terminal: true
    generate_summary: true
```

#### `backend/app/workflows/policy_rag.yaml`

```yaml
name: policy_rag
description: Answer customer knowledge questions from policy documents using RAG.
entry_step: classify_query

steps:
  classify_query:
    goal: Determine if the question is answerable from the knowledge base.
    action: rag_classify
    on_success: retrieve_and_answer
    branch:
      requires_account: authenticate

  authenticate:
    goal: Verify identity if the question requires account-specific context.
    tool: lookup_customer
    on_success: retrieve_and_answer

  retrieve_and_answer:
    goal: Retrieve relevant policy chunks and answer with citations.
    action: rag
    rag_top_k: 3
    on_success: confirm
    terminal: false

  confirm:
    goal: Confirm the answer was helpful or offer further assistance.
    terminal: true
```

---

### 2.4 WebSocket Event Contract — `frontend/src/wsTypes.ts`

```typescript
/**
 * WebSocket Event Contract
 * Client ↔ Server bidirectional JSON message types.
 * Frozen in Week 1 so frontend and backend can build independently.
 */

// ─── CLIENT → SERVER ─────────────────────────────────────────────────────────

export interface ClientControlStart {
  type: "control";
  action: "start";
  session_id?: string; // Resume existing session if provided
}

export interface ClientControlStop {
  type: "control";
  action: "stop";
}

export interface ClientControlBargeIn {
  type: "control";
  action: "barge_in"; // Interrupt AI mid-speech
}

export interface ClientAudioChunk {
  type: "audio_chunk";
  seq: number;          // Monotonic sequence number
  data: string;         // Base64-encoded PCM 16kHz mono audio
  sample_rate?: number; // Defaults to 16000
}

export interface ClientTextInput {
  type: "text_input"; // Dev mode: bypass STT
  text: string;
}

export type ClientMessage =
  | ClientControlStart
  | ClientControlStop
  | ClientControlBargeIn
  | ClientAudioChunk
  | ClientTextInput;

// ─── SERVER → CLIENT ─────────────────────────────────────────────────────────

export interface ServerTranscriptPartial {
  type: "transcript_partial";
  text: string;
  confidence?: number;
}

export interface ServerTranscriptFinal {
  type: "transcript_final";
  text: string;
  confidence: number;
}

export interface ServerAssistantText {
  type: "assistant_text";
  text: string;
  is_streaming: boolean; // True while tokens are still arriving
  rag_citations?: RagCitation[];
}

export interface ServerAudioChunk {
  type: "audio_chunk";
  seq: number;
  data: string; // Base64-encoded PCM audio
  sample_rate: number;
}

export interface ServerStateUpdate {
  type: "state_update";
  workflow_name: string | null;
  workflow_step: string | null;
  completed_steps: string[];
  flags: {
    ticket_created: boolean;
    engineer_booked: boolean;
    escalated: boolean;
    awaiting_approval: boolean;
    refund_triggered: boolean;
  };
  sentiment: "neutral" | "frustrated" | "angry" | "satisfied";
  customer_tier: string | null;
}

export interface ServerTicket {
  type: "ticket";
  id: string;         // e.g. "INC-10284"
  ticket_type: string;
  summary: string;
}

export interface ServerPolicyBlock {
  type: "policy_block";
  rule: string;
  message: string;    // Human-readable reason for the block
  required_action: string; // e.g. "await_manager_approval"
}

export interface ServerError {
  type: "error";
  code: string;
  message: string;
}

export interface ServerHandoffSummary {
  type: "handoff_summary";
  summary: string;
  ticket_id: string | null;
  sentiment: string;
}

export interface ServerObservability {
  type: "observability";
  turn: number;
  stage_latencies_ms: Record<string, number>;
  total_tokens: number;
  cost_usd: number;
  tool_calls: string[];
  intent: string | null;
}

export interface RagCitation {
  source: string;
  chunk: string;
  score: number;
}

export type ServerMessage =
  | ServerTranscriptPartial
  | ServerTranscriptFinal
  | ServerAssistantText
  | ServerAudioChunk
  | ServerStateUpdate
  | ServerTicket
  | ServerPolicyBlock
  | ServerError
  | ServerHandoffSummary
  | ServerObservability;
```

---

## Section 3 — Core LangGraph Orchestrator Loop {#section-3}

### `backend/app/orchestrator/graph.py`

```python
"""
LangGraph Orchestrator — the brain.
One turn runs through 6 nodes; every node reads/writes ConversationState.

Architecture:
  understand → route → plan → policy_check → execute → respond
                  ↑                    |
                  └── compound intents are decomposed here
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from langgraph.graph import StateGraph, END

from app.state import ConversationState
from app.orchestrator.nodes import (
    understand,
    router,
    plan,
    policy,
    execute,
    respond,
)


def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph state machine.
    Returns a compiled graph ready to be invoked per turn.
    """

    builder = StateGraph(dict)  # We pass state as a plain dict for Redis compatibility

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("understand", understand.node)
    builder.add_node("route",      router.node)
    builder.add_node("plan",       plan.node)
    builder.add_node("policy",     policy.node)
    builder.add_node("execute",    execute.node)
    builder.add_node("respond",    respond.node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    builder.set_entry_point("understand")

    # ── Linear edges (always) ─────────────────────────────────────────────────
    builder.add_edge("understand", "route")
    builder.add_edge("route",      "plan")

    # ── Conditional: plan → policy check OR skip to execute ──────────────────
    builder.add_conditional_edges(
        "plan",
        _route_after_plan,
        {
            "policy_check": "policy",
            "execute":       "execute",  # RAG / clarification / escalation skip policy
        }
    )

    # ── Conditional: policy → execute or end (blocked) ───────────────────────
    builder.add_conditional_edges(
        "policy",
        _route_after_policy,
        {
            "execute": "execute",
            "blocked": "respond",   # Policy blocked → generate blocking response
        }
    )

    builder.add_edge("execute", "respond")
    builder.add_edge("respond", END)

    return builder.compile()


# ─── Edge routing functions ────────────────────────────────────────────────────

def _route_after_plan(state: dict) -> Literal["policy_check", "execute"]:
    """
    Tool calls go through the policy gate first.
    RAG queries, clarifications, and escalations bypass it.
    """
    action_kind = state.get("planned_action", {}).get("kind", "ask")
    if action_kind == "tool":
        return "policy_check"
    return "execute"


def _route_after_policy(state: dict) -> Literal["execute", "blocked"]:
    """
    If the policy engine blocked the action, route straight to response
    generation to inform the customer (no tool runs).
    """
    if state.get("policy_verdict", {}).get("blocked", False):
        return "blocked"
    return "execute"


# ─── Public API ───────────────────────────────────────────────────────────────

# Singleton compiled graph (build once, invoke per turn)
_graph = build_graph()


async def run_turn(
    conversation_state: ConversationState,
    transcript: str,
    stream_callback=None,
) -> ConversationState:
    """
    Execute one complete orchestrator turn.

    Args:
        conversation_state: Current session state from Redis.
        transcript:         Final STT transcript for this turn.
        stream_callback:    Async callable(text_chunk) for streaming TTS.

    Returns:
        Updated ConversationState to persist back to Redis.
    """
    input_dict = {
        "state": conversation_state.model_dump(),
        "transcript": transcript,
        "stream_callback": stream_callback,
    }

    result = await _graph.ainvoke(input_dict)

    # Deserialise updated state dict back into Pydantic model
    updated_state = ConversationState.model_validate(result["state"])
    updated_state.turn_count += 1
    return updated_state
```

---

### `backend/app/orchestrator/nodes/understand.py`

```python
"""
Node 1: UNDERSTAND
Extract intent, secondary intents, entities, and sentiment from the transcript.
Uses a small, fast LLM.  Pure classification — never generates prose.
"""

from __future__ import annotations
import json
import time

from openai import AsyncOpenAI
from app.config import settings
from app.telemetry import log_stage

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

UNDERSTAND_PROMPT = """You are an intent extraction engine for a telecom contact centre.
Analyse the customer statement and return ONLY valid JSON with this exact schema:

{
  "primary_intent": "<one of: technical_support | billing | refund | complaint | policy_query | password_reset | general | unknown>",
  "secondary_intents": ["<additional intents if compound>"],
  "confidence": <0.0-1.0>,
  "sentiment": "<neutral | frustrated | angry | satisfied>",
  "entities": {
    "account_no": "<if mentioned>",
    "amount": "<monetary amount if mentioned as number>",
    "area_code": "<if mentioned>",
    "reason": "<brief reason phrase>"
  }
}

Rules:
- If multiple issues are mentioned, list ALL in secondary_intents
- Confidence below 0.65 should be reported accurately; the system will ask for clarification
- Sentiment 'angry' = explicit frustration or threatening language
- Never return anything other than the JSON object

Customer statement: "{transcript}"
"""


async def node(state: dict) -> dict:
    t0 = time.perf_counter()
    transcript = state["transcript"]
    conv_state = state["state"]

    prompt = UNDERSTAND_PROMPT.format(transcript=transcript)

    response = await client.chat.completions.create(
        model=settings.UNDERSTAND_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
        max_tokens=256,
    )

    raw = response.choices[0].message.content
    extracted = json.loads(raw)

    # Write to state
    conv_state["intent"]["name"] = extracted.get("primary_intent", "unknown")
    conv_state["intent"]["confidence"] = extracted.get("confidence", 0.0)
    conv_state["intent"]["entities"] = extracted.get("entities", {})
    conv_state["intent"]["secondary_intents"] = extracted.get("secondary_intents", [])
    conv_state["sentiment"] = extracted.get("sentiment", "neutral")

    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("understand", latency_ms, tokens=response.usage.total_tokens)

    state["state"] = conv_state
    state["understand_result"] = extracted
    return state
```

---

### `backend/app/orchestrator/nodes/router.py`

```python
"""
Node 2: MULTI-INTENT ROUTER
- If confidence < threshold → ask for clarification
- If compound intents → decompose into prioritised queue
- Select (or continue) the active workflow
"""

from __future__ import annotations
from app.workflows.loader import load_workflow

CONFIDENCE_THRESHOLD = 0.65

INTENT_TO_WORKFLOW = {
    "technical_support": "technical_support",
    "billing":           "billing_refund",
    "refund":            "billing_refund",
    "policy_query":      "policy_rag",
    "complaint":         "technical_support",  # Default to support flow
    "password_reset":    "technical_support",
}


async def node(state: dict) -> dict:
    conv_state = state["state"]
    intent = conv_state["intent"]

    # ── 1. Low confidence → ask clarification ────────────────────────────────
    if intent["confidence"] < CONFIDENCE_THRESHOLD:
        state["planned_action"] = {
            "kind": "ask",
            "question": (
                "I want to make sure I help you with the right thing. "
                "Could you tell me more about what you need today?"
            )
        }
        return state

    # ── 2. Compound intent decomposition ─────────────────────────────────────
    all_intents = [intent["name"]] + intent.get("secondary_intents", [])
    if len(all_intents) > 1 and not conv_state.get("intent_queue"):
        # Prioritise: billing > technical > policy
        priority_order = ["billing", "refund", "technical_support", "complaint",
                          "policy_query", "general"]
        sorted_intents = sorted(
            all_intents,
            key=lambda i: priority_order.index(i) if i in priority_order else 99
        )
        conv_state["intent_queue"] = sorted_intents
        conv_state["intent"]["name"] = sorted_intents[0]

    # ── 3. Select workflow if none active ────────────────────────────────────
    if not conv_state["workflow"]["name"]:
        workflow_name = INTENT_TO_WORKFLOW.get(conv_state["intent"]["name"])
        if workflow_name:
            wf = load_workflow(workflow_name)
            conv_state["workflow"]["name"] = wf.name
            conv_state["workflow"]["step"] = wf.entry_step

    state["state"] = conv_state
    return state
```

---

### `backend/app/orchestrator/nodes/plan.py`

```python
"""
Node 3: PLAN
Given the current workflow step and state, decide the next action:
  - tool call
  - rag retrieval
  - ask clarification
  - escalate
"""

from __future__ import annotations
import json
import time

from openai import AsyncOpenAI
from app.config import settings
from app.workflows.loader import load_workflow
from app.telemetry import log_stage

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PLAN_PROMPT = """You are the planning component of an enterprise AI contact centre orchestrator.
Your job is to decide the NEXT ACTION based on the current conversation state.

CURRENT STATE:
- Intent: {intent_name} (confidence: {confidence})
- Workflow: {workflow_name}, Step: {current_step}
- Customer verified: {customer_verified}
- Sentiment: {sentiment}
- Flags: {flags}
- Last tool result: {last_tool_result}

STEP GOAL: {step_goal}

AVAILABLE ACTIONS for this step:
{available_actions}

Rules:
1. If the step action is "rag", always choose kind="rag"
2. If the step tool is defined, choose kind="tool" with that tool name
3. If you need info you don't have, choose kind="ask"
4. If sentiment is "angry" and no resolution is in progress, choose kind="escalate"
5. NEVER invent tool arguments. Use ONLY what is in the state entities.

Return ONLY valid JSON:
{{
  "kind": "<tool | rag | ask | escalate>",
  "tool_name": "<tool name if kind=tool>",
  "tool_args": {{<arguments from state entities>}},
  "rag_query": "<query string if kind=rag>",
  "ask_text": "<clarifying question if kind=ask>",
  "reasoning": "<one sentence>"
}}
"""


async def node(state: dict) -> dict:
    t0 = time.perf_counter()
    conv_state = state["state"]

    workflow_name = conv_state["workflow"]["name"]
    current_step = conv_state["workflow"]["step"]

    # Load step definition
    step_goal = "Complete the current step."
    available_actions = "[]"
    if workflow_name and current_step:
        wf = load_workflow(workflow_name)
        step_def = wf.steps.get(current_step, {})
        step_goal = step_def.get("goal", step_goal)

        if step_def.get("action") == "rag":
            state["planned_action"] = {"kind": "rag", "rag_query": _build_rag_query(step_def, conv_state)}
            return state

        available_tools = []
        if step_def.get("tool"):
            available_tools.append(step_def["tool"])
        available_actions = json.dumps(available_tools)

    prompt = PLAN_PROMPT.format(
        intent_name=conv_state["intent"]["name"],
        confidence=conv_state["intent"]["confidence"],
        workflow_name=workflow_name,
        current_step=current_step,
        customer_verified=conv_state["customer"]["verified"],
        sentiment=conv_state["sentiment"],
        flags=json.dumps(conv_state["flags"]),
        last_tool_result=json.dumps(conv_state["working_memory"].get("last_tool_result", {})),
        step_goal=step_goal,
        available_actions=available_actions,
    )

    response = await client.chat.completions.create(
        model=settings.PLAN_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
        max_tokens=256,
    )

    planned = json.loads(response.choices[0].message.content)
    state["planned_action"] = planned
    state["state"] = conv_state

    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("plan", latency_ms, tokens=response.usage.total_tokens)
    return state


def _build_rag_query(step_def: dict, conv_state: dict) -> str:
    template = step_def.get("rag_query_template", "{query}")
    reason = conv_state["intent"]["entities"].get("reason", "")
    return template.format(reason=reason, query=conv_state["intent"]["name"])
```

---

### `backend/app/orchestrator/nodes/policy.py`

```python
"""
Node 4: POLICY ENGINE CHECK
Deterministic gate. Runs BEFORE any tool executes.
The LLM is NEVER asked whether a rule applies.
"""

from __future__ import annotations
from app.policies.engine import PolicyEngine

_engine = PolicyEngine()


async def node(state: dict) -> dict:
    conv_state = state["state"]
    planned_action = state.get("planned_action", {})

    verdict = _engine.evaluate(planned_action, conv_state)
    state["policy_verdict"] = verdict

    if verdict["blocked"]:
        # Rewrite the action to the required alternative
        state["planned_action"] = verdict["required_action"]
        # Update state flags
        if verdict["required_action"].get("kind") == "await_approval":
            conv_state["flags"]["awaiting_approval"] = True
        elif verdict["required_action"].get("kind") == "escalate":
            conv_state["flags"]["escalated"] = True
        state["state"] = conv_state

    return state
```

---

### `backend/app/orchestrator/nodes/execute.py`

```python
"""
Node 5: EXECUTE
Dispatch the planned action to a tool or RAG retriever.
Applies the result to the conversation state.
"""

from __future__ import annotations
import importlib
import asyncio
import time

from app.rag.retriever import retrieve
from app.workflows.executor import advance_workflow
from app.telemetry import log_stage


async def node(state: dict) -> dict:
    t0 = time.perf_counter()
    conv_state = state["state"]
    action = state["planned_action"]
    kind = action.get("kind")

    # ── TOOL CALL ─────────────────────────────────────────────────────────────
    if kind == "tool":
        tool_name = action["tool_name"]
        tool_args = action.get("tool_args", {})

        # Inject customer_id and session context where needed
        tool_args.setdefault("customer_id", conv_state["customer"]["customer_id"])
        tool_args.setdefault("session_id", conv_state["session_id"])

        tool_result = await _call_tool(tool_name, tool_args)
        state["execution_result"] = {"kind": "tool", "tool": tool_name, "result": tool_result}

        # Apply result to state
        conv_state["working_memory"]["last_tool_result"] = tool_result
        conv_state["metrics"]["tool_calls_made"].append(tool_name)

        # Advance workflow
        conv_state = advance_workflow(conv_state, tool_result)

    # ── RAG RETRIEVAL ─────────────────────────────────────────────────────────
    elif kind == "rag":
        rag_result = await retrieve(action.get("rag_query", ""))
        state["execution_result"] = {"kind": "rag", "result": rag_result}
        conv_state["flags"]["rag_used"] = True

    # ── CLARIFICATION / ASK ───────────────────────────────────────────────────
    elif kind == "ask":
        state["execution_result"] = {"kind": "ask", "text": action.get("ask_text", "")}

    # ── ESCALATION ────────────────────────────────────────────────────────────
    elif kind in ("escalate", "await_approval"):
        summary = _build_handoff_summary(conv_state)
        conv_state["handoff_summary"] = summary
        conv_state["flags"]["escalated"] = True
        state["execution_result"] = {"kind": "escalate", "summary": summary}

    state["state"] = conv_state
    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("execute", latency_ms)
    return state


async def _call_tool(tool_name: str, args: dict) -> dict:
    """Dynamically load and call a tool by name."""
    try:
        module = importlib.import_module(f"app.tools.{tool_name}")
        func = getattr(module, tool_name)
        # Support both sync and async tools
        if asyncio.iscoroutinefunction(func):
            return await func(**args)
        return await asyncio.get_event_loop().run_in_executor(None, lambda: func(**args))
    except Exception as e:
        return {"ok": False, "data": {}, "error": str(e)}


def _build_handoff_summary(state: dict) -> str:
    return (
        f"Customer: {state['customer'].get('name', 'Unknown')} "
        f"(ID: {state['customer'].get('customer_id', 'N/A')}, "
        f"Tier: {state['customer'].get('tier', 'standard')})\n"
        f"Intent: {state['intent']['name']}\n"
        f"Workflow: {state['workflow']['name']}, Step: {state['workflow']['step']}\n"
        f"Completed: {', '.join(state['workflow']['completed_steps'])}\n"
        f"Sentiment: {state['sentiment']}\n"
        f"Flags: {state['flags']}\n"
        f"Ticket: {state.get('ticket_id', 'None')}"
    )
```

---

### `backend/app/orchestrator/nodes/respond.py`

```python
"""
Node 6: RESPOND
Generate a concise, empathetic, TTS-optimised reply.
The LLM receives STRUCTURED context — never raw conversation history.
This is LLM call #3 per turn.
"""

from __future__ import annotations
import time
from typing import Optional, Callable, Awaitable

from openai import AsyncOpenAI
from app.config import settings
from app.telemetry import log_stage

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

RESPOND_PROMPT = """You are the voice of an enterprise AI contact centre assistant.
Generate a SINGLE spoken response based ONLY on the structured context below.

Context:
- Intent: {intent}
- Workflow step: {step}
- Customer tier: {tier}
- Sentiment: {sentiment}
- Action taken: {action_kind}
- Tool result: {tool_result}
- RAG answer: {rag_answer}
- Policy block reason: {policy_block}
- Ticket ID: {ticket_id}

Rules for your response:
1. Keep it under 3 sentences — it will be spoken aloud
2. Never invent ticket numbers, dates, or amounts. Use only those in context
3. If sentiment is frustrated/angry, open with empathy
4. If RAG was used, cite the source naturally ("According to our policy...")
5. If policy blocked an action, explain what happens next (e.g., manager approval)
6. If a ticket was created, mention it
7. Avoid corporate jargon. Sound human and helpful
8. End with a natural offer to help further, if appropriate

Respond with ONLY the spoken text — no labels, no JSON, no quotes.
"""


async def node(state: dict) -> dict:
    t0 = time.perf_counter()
    conv_state = state["state"]
    execution_result = state.get("execution_result", {})
    policy_verdict = state.get("policy_verdict", {})
    stream_callback: Optional[Callable] = state.get("stream_callback")

    # Extract ticket ID if created
    ticket_id = None
    if execution_result.get("kind") == "tool":
        tool_data = execution_result["result"].get("data", {})
        ticket_id = tool_data.get("ticket_id")
        if ticket_id:
            conv_state["flags"]["ticket_created"] = True

    # Build structured context for the LLM
    rag_answer = ""
    if execution_result.get("kind") == "rag":
        chunks = execution_result["result"].get("chunks", [])
        rag_answer = " ".join(c["text"] for c in chunks[:2])

    policy_block = ""
    if policy_verdict.get("blocked"):
        policy_block = policy_verdict.get("reason", "Policy block applied.")

    prompt = RESPOND_PROMPT.format(
        intent=conv_state["intent"]["name"],
        step=conv_state["workflow"]["step"],
        tier=conv_state["customer"]["tier"] or "standard",
        sentiment=conv_state["sentiment"],
        action_kind=execution_result.get("kind", "unknown"),
        tool_result=str(execution_result.get("result", {}))[:200],
        rag_answer=rag_answer[:400],
        policy_block=policy_block,
        ticket_id=ticket_id or conv_state.get("ticket_id", "None"),
    )

    response_text = ""

    if stream_callback:
        # Stream tokens → send to TTS as they arrive
        stream = await client.chat.completions.create(
            model=settings.GENERATE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=120,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            response_text += delta
            if delta:
                await stream_callback(delta)
    else:
        response = await client.chat.completions.create(
            model=settings.GENERATE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=120,
        )
        response_text = response.choices[0].message.content or ""
        log_stage("generate", (time.perf_counter() - t0) * 1000,
                  tokens=response.usage.total_tokens)

    # Save to transcript
    citations = []
    if execution_result.get("kind") == "rag":
        citations = [c.get("source", "") for c in execution_result["result"].get("chunks", [])]

    conv_state.setdefault("transcript", []).append({
        "role": "assistant",
        "text": response_text,
        "rag_citations": citations,
    })

    state["generated_reply"] = response_text
    state["reply_citations"] = citations
    state["ticket_id"] = ticket_id
    state["state"] = conv_state
    return state
```

---

## Section 4 — Policy Engine & Enterprise Mock Tools {#section-4}

### `backend/app/policies/engine.py`

```python
"""
Deterministic Policy Engine.
Evaluates a set of hard-coded business rules BEFORE any tool runs.
The LLM is NEVER consulted here.  Rules are checked in priority order.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyVerdict:
    blocked: bool
    reason: str = ""
    required_action: dict = None

    def __post_init__(self):
        if self.required_action is None:
            self.required_action = {}


class PolicyEngine:
    """
    Evaluates business rules in priority order.
    Returns a verdict: allow or block with a required alternative action.
    """

    def evaluate(self, action: dict, state: dict) -> dict:
        """
        Evaluate all rules against the planned action and current state.

        Returns a plain dict for JSON serialisability:
        {
          "blocked": bool,
          "reason": str,
          "required_action": dict | None
        }
        """
        checks = [
            self._check_large_refund,
            self._check_angry_customer,
            self._check_diagnostics_threshold,
            self._check_unverified_customer,
            self._check_repeated_failures,
        ]

        for check in checks:
            verdict = check(action, state)
            if verdict.blocked:
                return {
                    "blocked": True,
                    "reason": verdict.reason,
                    "required_action": verdict.required_action,
                }

        return {"blocked": False, "reason": "", "required_action": None}

    # ── Individual rules ──────────────────────────────────────────────────────

    def _check_large_refund(self, action: dict, state: dict) -> PolicyVerdict:
        """
        Rule: refund_payment with amount > ₹10,000 requires manager approval.
        """
        if action.get("tool_name") != "refund_payment":
            return PolicyVerdict(blocked=False)

        amount = float(action.get("tool_args", {}).get("amount", 0))
        if amount > 10_000:
            return PolicyVerdict(
                blocked=True,
                reason=f"Refund of ₹{amount:,.0f} exceeds ₹10,000 limit — manager approval required.",
                required_action={
                    "kind": "await_approval",
                    "message": (
                        f"This refund of ₹{amount:,.0f} requires manager approval. "
                        "I'll escalate this and you'll receive confirmation within 24 hours."
                    ),
                    "escalation_tier": "manager",
                }
            )
        return PolicyVerdict(blocked=False)

    def _check_angry_customer(self, action: dict, state: dict) -> PolicyVerdict:
        """
        Rule: If sentiment is 'angry' and we haven't already escalated, escalate now.
        """
        if (state.get("sentiment") == "angry"
                and not state.get("flags", {}).get("escalated", False)
                and action.get("kind") not in ("escalate", "ask")):
            return PolicyVerdict(
                blocked=True,
                reason="Customer sentiment is 'angry'. Escalating to human agent.",
                required_action={
                    "kind": "escalate",
                    "message": (
                        "I completely understand your frustration and I sincerely apologise. "
                        "Let me connect you with a senior specialist right away."
                    ),
                }
            )
        return PolicyVerdict(blocked=False)

    def _check_diagnostics_threshold(self, action: dict, state: dict) -> PolicyVerdict:
        """
        Rule: After 3 failed diagnostics, force an engineer visit (do not retry).
        """
        diagnostics_run = state.get("working_memory", {}).get("diagnostics_run", 0)
        if (action.get("tool_name") == "run_diagnostics"
                and diagnostics_run >= 3):
            return PolicyVerdict(
                blocked=True,
                reason="3 diagnostic attempts exhausted. Engineer visit required.",
                required_action={
                    "kind": "tool",
                    "tool_name": "book_engineer",
                    "tool_args": {
                        "reason": "3 remote diagnostics failed",
                        "priority": "high",
                    },
                    "message": (
                        "We've tried remote diagnostics three times and the issue persists. "
                        "I'm arranging an engineer visit as the next step."
                    ),
                }
            )
        return PolicyVerdict(blocked=False)

    def _check_unverified_customer(self, action: dict, state: dict) -> PolicyVerdict:
        """
        Rule: Do not execute financial tools on unverified customers.
        """
        financial_tools = {"refund_payment", "lookup_invoice", "cancel_order"}
        if (action.get("tool_name") in financial_tools
                and not state.get("customer", {}).get("verified", False)):
            return PolicyVerdict(
                blocked=True,
                reason="Customer identity not verified. Cannot process financial action.",
                required_action={
                    "kind": "tool",
                    "tool_name": "lookup_customer",
                    "tool_args": {},
                    "message": (
                        "Before I can process this, I need to verify your account. "
                        "Could you please provide your account number or registered phone?"
                    ),
                }
            )
        return PolicyVerdict(blocked=False)

    def _check_repeated_failures(self, action: dict, state: dict) -> PolicyVerdict:
        """
        Rule: If a tool has failed 2+ times in this session, escalate.
        """
        tool_name = action.get("tool_name", "")
        step_attempts = state.get("workflow", {}).get("step_attempts", {})
        current_step = state.get("workflow", {}).get("step", "")

        if step_attempts.get(current_step, 0) >= 2:
            return PolicyVerdict(
                blocked=True,
                reason=f"Tool '{tool_name}' has failed {step_attempts[current_step]} times. Escalating.",
                required_action={
                    "kind": "escalate",
                    "message": (
                        "I'm having difficulty completing this automatically. "
                        "Let me get a specialist on the line for you."
                    ),
                }
            )
        return PolicyVerdict(blocked=False)
```

---

### Mock Tools FastAPI Endpoints — `backend/app/tools/`

#### `backend/app/tools/lookup_customer.py`

```python
"""Mock: Lookup customer by account number or phone."""
import random
from app.tools.contracts import ToolResult, ok_result, err_result

# In-memory mock database
MOCK_CUSTOMERS = {
    "ACC001": {
        "customer_id": "ACC001",
        "name": "Priya Sharma",
        "tier": "premium",
        "phone": "+919876543210",
        "area_code": "MH400001",
        "email": "priya.sharma@example.com",
    },
    "ACC002": {
        "customer_id": "ACC002",
        "name": "Rahul Verma",
        "tier": "standard",
        "phone": "+919123456789",
        "area_code": "DL110001",
        "email": "rahul.verma@example.com",
    },
}


def lookup_customer(
    account_no: str = None,
    phone: str = None,
    customer_id: str = None,
    **kwargs
) -> ToolResult:
    # Find by any identifier
    for cid, cdata in MOCK_CUSTOMERS.items():
        if (account_no and cdata["customer_id"] == account_no) or \
           (phone and cdata["phone"] == phone) or \
           (customer_id and cid == customer_id):
            return ok_result({
                **cdata,
                "verified": True,
                "lookup_method": "account_no" if account_no else "phone",
            })

    # Demo: auto-succeed with a generic customer to keep demos running
    return ok_result({
        "customer_id": "ACC999",
        "name": "Demo Customer",
        "tier": "standard",
        "phone": phone or "unknown",
        "area_code": "GJ380001",
        "email": "demo@example.com",
        "verified": True,
        "lookup_method": "demo_fallback",
    })
```

---

#### `backend/app/tools/check_outage.py`

```python
"""Mock: Check for known network outages in an area."""
from app.tools.contracts import ToolResult, ok_result

ACTIVE_OUTAGES = {
    "MH400002": {
        "outage_id": "OUT-4521",
        "description": "Fibre cable cut on Link Road. Crews on-site.",
        "eta_hours": 4,
    }
}


def check_outage(area_code: str = None, customer_id: str = None, **kwargs) -> ToolResult:
    if area_code and area_code in ACTIVE_OUTAGES:
        return ok_result({
            "outage": True,
            "outage_found": True,
            **ACTIVE_OUTAGES[area_code],
        })
    return ok_result({
        "outage": False,
        "outage_found": False,
        "message": "No known outages in your area.",
    })
```

---

#### `backend/app/tools/run_diagnostics.py`

```python
"""Mock: Run remote diagnostic tests on customer equipment."""
import random
from app.tools.contracts import ToolResult, ok_result, err_result

DIAGNOSTIC_SCENARIOS = [
    {"passed": True,  "signal_strength": "good",  "issue_found": False},
    {"passed": False, "signal_strength": "weak",  "issue_found": True,  "issue": "Low SNR on line"},
    {"passed": False, "signal_strength": "none",  "issue_found": True,  "issue": "Router not responding"},
]


def run_diagnostics(customer_id: str = None, session_id: str = None, **kwargs) -> ToolResult:
    # Simulate 30% pass rate for demo realism
    scenario = random.choices(DIAGNOSTIC_SCENARIOS, weights=[30, 40, 30])[0]

    if scenario["passed"]:
        return ok_result({
            "diagnostic_passed": True,
            "signal_strength": scenario["signal_strength"],
            "recommendation": "Connection looks healthy. Issue may have self-resolved.",
        })
    else:
        return ok_result({
            "diagnostic_passed": False,
            "signal_strength": scenario["signal_strength"],
            "issue_found": True,
            "issue": scenario.get("issue", "Unknown fault detected"),
            "recommendation": "Remote fix not possible. Consider engineer visit.",
        })
```

---

#### `backend/app/tools/book_engineer.py`

```python
"""Mock: Schedule a field engineer visit."""
import uuid
from datetime import datetime, timedelta
from app.tools.contracts import ToolResult, ok_result, err_result

def book_engineer(
    customer_id: str = None,
    reason: str = "Technical issue",
    priority: str = "standard",
    **kwargs
) -> ToolResult:
    # Mock appointment scheduler
    tomorrow = datetime.now() + timedelta(days=1)
    slot_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

    booking_ref = f"ENG-{uuid.uuid4().hex[:6].upper()}"

    return ok_result({
        "booking_ref": booking_ref,
        "engineer_booked": True,
        "appointment_datetime": slot_time.isoformat(),
        "appointment_display": slot_time.strftime("%A, %d %B at %I:%M %p"),
        "priority": priority,
        "reason": reason,
        "technician_name": "Raj Kumar",
        "contact_number": "+91-9000000001",
    })
```

---

#### `backend/app/tools/refund_payment.py`

```python
"""
Mock: Process a refund.
NOTE: Amounts > 10000 are BLOCKED by the policy engine before this is ever called.
"""
import uuid
from app.tools.contracts import ToolResult, ok_result, err_result


def refund_payment(
    customer_id: str = None,
    amount: float = 0,
    reason: str = "Customer request",
    invoice_id: str = None,
    **kwargs
) -> ToolResult:
    if amount <= 0:
        return err_result("Refund amount must be greater than 0.")

    if amount > 10_000:
        # Belt-and-suspenders: policy engine should have caught this
        return err_result("Refund amount exceeds policy limit. Manager approval required.")

    refund_ref = f"REF-{uuid.uuid4().hex[:8].upper()}"

    return ok_result({
        "refund_ref": refund_ref,
        "refund_triggered": True,
        "amount": amount,
        "currency": "INR",
        "reason": reason,
        "invoice_id": invoice_id,
        "processing_days": 3,
        "message": f"Refund of ₹{amount:,.2f} initiated. Reference: {refund_ref}",
    })
```

---

#### `backend/app/tools/create_ticket.py`

```python
"""Mock: Create a support ticket."""
import uuid
import random
from datetime import datetime, timezone
from app.tools.contracts import ToolResult, ok_result


def create_ticket(
    customer_id: str = None,
    session_id: str = None,
    intent: str = "general",
    summary: str = "",
    priority: str = "medium",
    ticket_type: str = "incident",
    **kwargs
) -> ToolResult:
    ticket_id = f"INC-{random.randint(10000, 99999)}"

    return ok_result({
        "ticket_id": ticket_id,
        "ticket_created": True,
        "ticket_type": ticket_type,
        "priority": priority,
        "summary": summary or f"Auto-created for session {session_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sla_hours": 4 if priority == "high" else 24,
        "status": "open",
    })
```

---

#### `backend/app/tools/router.py` (FastAPI sub-app)

```python
"""FastAPI router mounting all mock tool endpoints for direct HTTP access."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.tools import (
    lookup_customer, check_outage, run_diagnostics,
    book_engineer, refund_payment, create_ticket
)

router = APIRouter(prefix="/tools", tags=["Mock Enterprise Tools"])


class LookupCustomerRequest(BaseModel):
    account_no: Optional[str] = None
    phone: Optional[str] = None
    customer_id: Optional[str] = None

class CheckOutageRequest(BaseModel):
    area_code: str
    customer_id: Optional[str] = None

class RunDiagnosticsRequest(BaseModel):
    customer_id: Optional[str] = None
    session_id: Optional[str] = None

class BookEngineerRequest(BaseModel):
    customer_id: Optional[str] = None
    reason: Optional[str] = "Technical issue"
    priority: Optional[str] = "standard"

class RefundPaymentRequest(BaseModel):
    customer_id: Optional[str] = None
    amount: float
    reason: Optional[str] = "Customer request"
    invoice_id: Optional[str] = None

class CreateTicketRequest(BaseModel):
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = "general"
    summary: Optional[str] = ""
    priority: Optional[str] = "medium"


@router.post("/lookup_customer")
def api_lookup_customer(req: LookupCustomerRequest):
    return lookup_customer.lookup_customer(**req.dict())

@router.post("/check_outage")
def api_check_outage(req: CheckOutageRequest):
    return check_outage.check_outage(**req.dict())

@router.post("/run_diagnostics")
def api_run_diagnostics(req: RunDiagnosticsRequest):
    return run_diagnostics.run_diagnostics(**req.dict())

@router.post("/book_engineer")
def api_book_engineer(req: BookEngineerRequest):
    return book_engineer.book_engineer(**req.dict())

@router.post("/refund_payment")
def api_refund_payment(req: RefundPaymentRequest):
    return refund_payment.refund_payment(**req.dict())

@router.post("/create_ticket")
def api_create_ticket(req: CreateTicketRequest):
    return create_ticket.create_ticket(**req.dict())
```

---

### `backend/app/main.py` — FastAPI Gateway

```python
"""
FastAPI entry point.
- REST API for tool endpoints
- WebSocket endpoint for voice/text sessions
"""

import asyncio
import json
import redis.asyncio as aioredis

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.state import ConversationState
from app.orchestrator.graph import run_turn
from app.tools.router import router as tools_router
from app.telemetry import log_turn_start

app = FastAPI(title="AI Contact Centre", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools_router)

# Redis connection pool
redis_client: aioredis.Redis = None

@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    await redis_client.aclose()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    # Load or create session state
    raw = await redis_client.get(f"session:{session_id}")
    if raw:
        state = ConversationState.from_redis(raw)
    else:
        state = ConversationState(session_id=session_id)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "control" and msg.get("action") == "start":
                await ws.send_json({"type": "state_update",
                                    "workflow_step": state.workflow.step,
                                    "completed_steps": state.workflow.completed_steps,
                                    "flags": state.flags.dict()})

            elif msg_type == "transcript_final" or msg_type == "text_input":
                transcript = msg.get("text", "")
                log_turn_start(session_id, transcript)
                state.add_transcript("user", transcript)

                # Streaming TTS callback → send audio_chunk events
                token_buffer = []
                async def stream_callback(token: str):
                    token_buffer.append(token)
                    await ws.send_json({
                        "type": "assistant_text",
                        "text": token,
                        "is_streaming": True,
                    })

                state = await run_turn(state, transcript, stream_callback)

                # Push final state update
                await ws.send_json({
                    "type": "state_update",
                    "workflow_name": state.workflow.name,
                    "workflow_step": state.workflow.step,
                    "completed_steps": state.workflow.completed_steps,
                    "flags": state.flags.dict(),
                    "sentiment": state.sentiment,
                    "customer_tier": state.customer.tier,
                })

                # Push ticket if created
                if state.flags.ticket_created:
                    last_result = state.working_memory.last_tool_result or {}
                    ticket_id = last_result.get("data", {}).get("ticket_id")
                    if ticket_id:
                        await ws.send_json({"type": "ticket", "id": ticket_id})

                # Persist state to Redis
                await redis_client.setex(
                    f"session:{session_id}",
                    3600,  # 1 hour TTL
                    state.to_redis()
                )

    except WebSocketDisconnect:
        await redis_client.setex(
            f"session:{session_id}", 86400, state.to_redis()
        )
```

---

### `backend/app/rag/retriever.py`

```python
"""
RAG Retriever — FAISS-backed similarity search with source citations.
"""

import os
import pickle
from pathlib import Path

import numpy as np
import faiss
from openai import AsyncOpenAI

from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

INDEX_PATH = Path("app/rag/faiss_index.pkl")


class RAGRetriever:
    def __init__(self):
        self.index = None
        self.chunks: list[dict] = []  # [{text, source, chunk_id}]
        self._load()

    def _load(self):
        if INDEX_PATH.exists():
            with open(INDEX_PATH, "rb") as f:
                data = pickle.load(f)
                self.index = data["index"]
                self.chunks = data["chunks"]

    async def retrieve(self, query: str, top_k: int = 3) -> dict:
        if not self.index or not self.chunks:
            return {"chunks": [], "error": "Index not loaded. Run indexer first."}

        # Embed the query
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_vec = np.array([response.data[0].embedding], dtype="float32")
        faiss.normalize_L2(query_vec)

        distances, indices = self.index.search(query_vec, top_k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self.chunks):
                results.append({
                    "text": self.chunks[idx]["text"],
                    "source": self.chunks[idx]["source"],
                    "score": float(score),
                })

        return {"chunks": results, "query": query}


_retriever = RAGRetriever()


async def retrieve(query: str, top_k: int = 3) -> dict:
    return await _retriever.retrieve(query, top_k)
```

---

## Section 5 — React + TypeScript UI Components {#section-5}

### `frontend/src/AudioClient.ts`

```typescript
/**
 * AudioClient — Microphone capture, WebSocket streaming, and chunked audio playback.
 * Handles the complete bidirectional audio pipeline.
 */

import type { ClientMessage, ServerMessage } from "./wsTypes";

export type SessionEventHandler = (msg: ServerMessage) => void;

export class AudioClient {
  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sequenceNumber = 0;
  private isRecording = false;
  private playbackQueue: AudioBuffer[] = [];
  private isPlaying = false;

  constructor(
    private readonly wsUrl: string,
    private readonly onMessage: SessionEventHandler,
    private readonly onStateChange: (state: "idle" | "recording" | "playing") => void
  ) {}

  // ── Connection ──────────────────────────────────────────────────────────────

  async connect(sessionId: string): Promise<void> {
    const url = `${this.wsUrl}/ws/${sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.send({ type: "control", action: "start", session_id: sessionId });
    };

    this.ws.onmessage = (event) => {
      const msg: ServerMessage = JSON.parse(event.data);
      this.handleServerMessage(msg);
      this.onMessage(msg);
    };

    this.ws.onerror = (err) => console.error("[AudioClient] WebSocket error:", err);
    this.ws.onclose = () => {
      console.log("[AudioClient] WebSocket closed.");
      this.stopRecording();
    };

    await this.initAudioContext();
  }

  disconnect(): void {
    this.stopRecording();
    this.ws?.close();
    this.audioContext?.close();
  }

  // ── Recording ──────────────────────────────────────────────────────────────

  async startRecording(): Promise<void> {
    if (this.isRecording) return;
    if (!this.audioContext) await this.initAudioContext();

    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    const source = this.audioContext!.createMediaStreamSource(this.mediaStream);

    // Load audio worklet for low-latency processing
    await this.audioContext!.audioWorklet.addModule("/audio-processor.js");
    this.workletNode = new AudioWorkletNode(this.audioContext!, "audio-processor");

    this.workletNode.port.onmessage = (event) => {
      if (event.data.type === "audio-chunk") {
        this.sendAudioChunk(event.data.buffer);
      }
    };

    source.connect(this.workletNode);
    this.workletNode.connect(this.audioContext!.destination);

    this.isRecording = true;
    this.onStateChange("recording");
  }

  stopRecording(): void {
    this.isRecording = false;
    this.mediaStream?.getTracks().forEach((t) => t.stop());
    this.workletNode?.disconnect();
    this.onStateChange("idle");
    this.send({ type: "control", action: "stop" });
  }

  // ── Text input (dev mode) ──────────────────────────────────────────────────

  sendText(text: string): void {
    this.send({ type: "text_input", text });
  }

  // ── Audio playback ─────────────────────────────────────────────────────────

  private async handleServerMessage(msg: ServerMessage): Promise<void> {
    if (msg.type === "audio_chunk") {
      const buffer = base64ToArrayBuffer(msg.data);
      const audioBuffer = await this.decodeAudioChunk(buffer, msg.sample_rate);
      this.enqueuePlayback(audioBuffer);
    }
  }

  private async decodeAudioChunk(
    buffer: ArrayBuffer,
    sampleRate: number
  ): Promise<AudioBuffer> {
    // PCM16 → Float32 conversion
    const pcm16 = new Int16Array(buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }

    const audioBuffer = this.audioContext!.createBuffer(1, float32.length, sampleRate);
    audioBuffer.getChannelData(0).set(float32);
    return audioBuffer;
  }

  private enqueuePlayback(buffer: AudioBuffer): void {
    this.playbackQueue.push(buffer);
    if (!this.isPlaying) {
      this.playNextChunk();
    }
  }

  private playNextChunk(): void {
    if (this.playbackQueue.length === 0) {
      this.isPlaying = false;
      this.onStateChange("idle");
      return;
    }

    this.isPlaying = true;
    this.onStateChange("playing");
    const buffer = this.playbackQueue.shift()!;
    const source = this.audioContext!.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext!.destination);
    source.onended = () => this.playNextChunk();
    source.start();
  }

  interruptPlayback(): void {
    this.playbackQueue = [];
    this.isPlaying = false;
    this.send({ type: "control", action: "barge_in" });
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  private async initAudioContext(): Promise<void> {
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
  }

  private sendAudioChunk(buffer: ArrayBuffer): void {
    const base64 = arrayBufferToBase64(buffer);
    this.send({
      type: "audio_chunk",
      seq: this.sequenceNumber++,
      data: base64,
      sample_rate: 16000,
    });
  }

  private send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
```

---

### `frontend/src/components/WorkflowProgressPanel.tsx`

```tsx
/**
 * WorkflowProgressPanel — Real-time workflow step visualiser.
 * Shows completed steps, active step, ticket badges, and policy alerts.
 */

import React from "react";
import type { ServerStateUpdate, ServerTicket, ServerPolicyBlock } from "../wsTypes";

interface WorkflowStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "failed";
}

interface Props {
  workflowName: string | null;
  currentStep: string | null;
  completedSteps: string[];
  ticket: ServerTicket | null;
  policyBlock: ServerPolicyBlock | null;
  sentiment: string;
  customerTier: string | null;
}

const WORKFLOW_STEP_LABELS: Record<string, Record<string, string>> = {
  technical_support: {
    authenticate:      "Customer Identified",
    check_outage:      "Outage Checked",
    run_diagnostics:   "Running Diagnostics",
    book_engineer:     "Booking Engineer",
    create_ticket:     "Creating Ticket",
    confirm:           "Confirmed",
    escalate:          "Escalated to Human",
  },
  billing_refund: {
    authenticate:            "Customer Identified",
    lookup_invoice:          "Invoice Retrieved",
    verify_refund_eligibility: "Eligibility Verified",
    refund_payment:          "Processing Refund",
    send_confirmation:       "Sending Confirmation",
    create_ticket:           "Ticket Created",
    confirm:                 "Confirmed",
    escalate:                "Escalated to Human",
  },
  policy_rag: {
    classify_query:       "Query Classified",
    authenticate:         "Customer Identified",
    retrieve_and_answer:  "Knowledge Retrieved",
    confirm:              "Confirmed",
  },
};

const SENTIMENT_CONFIG: Record<string, { color: string; icon: string; label: string }> = {
  neutral:    { color: "#64748b", icon: "😐", label: "Neutral" },
  frustrated: { color: "#f59e0b", icon: "😤", label: "Frustrated" },
  angry:      { color: "#ef4444", icon: "😠", label: "Angry" },
  satisfied:  { color: "#22c55e", icon: "😊", label: "Satisfied" },
};

export const WorkflowProgressPanel: React.FC<Props> = ({
  workflowName,
  currentStep,
  completedSteps,
  ticket,
  policyBlock,
  sentiment,
  customerTier,
}) => {
  const stepLabels = workflowName ? WORKFLOW_STEP_LABELS[workflowName] || {} : {};
  const allStepIds = Object.keys(stepLabels);

  const getStepStatus = (stepId: string): WorkflowStep["status"] => {
    if (completedSteps.includes(stepId)) return "completed";
    if (stepId === currentStep) return "active";
    return "pending";
  };

  const sentimentInfo = SENTIMENT_CONFIG[sentiment] || SENTIMENT_CONFIG.neutral;

  return (
    <div className="workflow-panel">
      {/* Header */}
      <div className="workflow-panel__header">
        <h3 className="workflow-panel__title">
          {workflowName
            ? workflowName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
            : "Waiting for input..."}
        </h3>
        {customerTier && (
          <span className={`tier-badge tier-badge--${customerTier}`}>
            {customerTier === "premium" ? "⭐ Premium" : "Standard"}
          </span>
        )}
      </div>

      {/* Sentiment indicator */}
      <div className="sentiment-bar" style={{ borderColor: sentimentInfo.color }}>
        <span className="sentiment-bar__icon">{sentimentInfo.icon}</span>
        <span className="sentiment-bar__label" style={{ color: sentimentInfo.color }}>
          {sentimentInfo.label}
        </span>
      </div>

      {/* Step progress */}
      <div className="workflow-steps">
        {allStepIds.map((stepId, index) => {
          const status = getStepStatus(stepId);
          return (
            <div
              key={stepId}
              className={`workflow-step workflow-step--${status}`}
              aria-label={`Step ${index + 1}: ${stepLabels[stepId]}, ${status}`}
            >
              <div className="workflow-step__connector" />
              <div className="workflow-step__dot">
                {status === "completed" && <CheckIcon />}
                {status === "active" && <PulsingDot />}
                {status === "pending" && <span className="workflow-step__number">{index + 1}</span>}
              </div>
              <span className="workflow-step__label">{stepLabels[stepId]}</span>
            </div>
          );
        })}
      </div>

      {/* Ticket badge */}
      {ticket && (
        <div className="ticket-badge" id="ticket-badge">
          <span className="ticket-badge__icon">🎫</span>
          <div>
            <div className="ticket-badge__id">{ticket.id}</div>
            <div className="ticket-badge__summary">{ticket.summary}</div>
          </div>
        </div>
      )}

      {/* Policy alert */}
      {policyBlock && (
        <div className="policy-alert">
          <span className="policy-alert__icon">🛡️</span>
          <div>
            <div className="policy-alert__rule">Policy Gate Active</div>
            <div className="policy-alert__message">{policyBlock.message}</div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Sub-components ─────────────────────────────────────────────────────────────

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}
    className="workflow-step__check-icon">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const PulsingDot = () => <div className="workflow-step__pulse" aria-live="polite" />;
```

---

### `frontend/src/components/TranscriptPanel.tsx`

```tsx
/**
 * TranscriptPanel — Live speech transcript with RAG citation tags.
 * Streams partial and final transcripts with smooth animations.
 */

import React, { useEffect, useRef } from "react";
import type { RagCitation } from "../wsTypes";

export interface TranscriptEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  isStreaming?: boolean;
  citations?: RagCitation[];
  timestamp: Date;
}

interface Props {
  entries: TranscriptEntry[];
  partialTranscript: string;
  connectionStatus: "connected" | "disconnected" | "connecting";
}

export const TranscriptPanel: React.FC<Props> = ({
  entries,
  partialTranscript,
  connectionStatus,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, partialTranscript]);

  return (
    <div className="transcript-panel" role="log" aria-live="polite" aria-label="Conversation transcript">
      {/* Connection status */}
      <div className={`connection-status connection-status--${connectionStatus}`} id="connection-status">
        <span className="connection-status__dot" />
        <span className="connection-status__label">
          {connectionStatus === "connected" ? "Connected" :
           connectionStatus === "connecting" ? "Connecting..." :
           "Disconnected"}
        </span>
      </div>

      {/* Transcript entries */}
      <div className="transcript-messages">
        {entries.map((entry) => (
          <TranscriptMessage key={entry.id} entry={entry} />
        ))}

        {/* Live partial transcript */}
        {partialTranscript && (
          <div className="transcript-message transcript-message--user transcript-message--partial">
            <div className="transcript-message__avatar">👤</div>
            <div className="transcript-message__bubble">
              <span className="transcript-message__text">{partialTranscript}</span>
              <span className="transcript-message__cursor" aria-hidden="true">|</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
};

// ── Message component ──────────────────────────────────────────────────────────

const TranscriptMessage: React.FC<{ entry: TranscriptEntry }> = ({ entry }) => {
  const isUser = entry.role === "user";

  return (
    <div
      className={`transcript-message transcript-message--${entry.role} ${
        entry.isStreaming ? "transcript-message--streaming" : ""
      }`}
      aria-label={`${isUser ? "Customer" : "AI Assistant"}: ${entry.text}`}
    >
      <div className="transcript-message__avatar">
        {isUser ? "👤" : "🤖"}
      </div>

      <div className="transcript-message__content">
        <div className="transcript-message__bubble">
          <span className="transcript-message__text">
            {entry.text}
            {entry.isStreaming && (
              <span className="transcript-message__streaming-dot" aria-hidden="true" />
            )}
          </span>
        </div>

        {/* RAG Citations */}
        {entry.citations && entry.citations.length > 0 && (
          <div className="rag-citations" aria-label="Source citations">
            <span className="rag-citations__label">📚 Sources:</span>
            {entry.citations.map((citation, i) => (
              <CitationTag key={i} citation={citation} />
            ))}
          </div>
        )}

        {/* Timestamp */}
        <time className="transcript-message__time" dateTime={entry.timestamp.toISOString()}>
          {entry.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </time>
      </div>
    </div>
  );
};

const CitationTag: React.FC<{ citation: RagCitation }> = ({ citation }) => (
  <div className="citation-tag" title={citation.chunk}>
    <span className="citation-tag__icon">📄</span>
    <span className="citation-tag__source">{citation.source}</span>
    <span className="citation-tag__score">{(citation.score * 100).toFixed(0)}%</span>
  </div>
);
```

---

## Section 6 — Phased Week-by-Week Implementation Plan {#section-6}

### 8-Week Execution Matrix

| Week | Owner A (AI Orchestrator Lead) | Owner B (Backend Lead) | Owner C (Frontend Lead) | Milestone |
|------|-------------------------------|----------------------|------------------------|-----------|
| **1** | Define 4 core contracts (state schema, tool interface, workflow format, WS event contract). Set up Redis + Postgres. Run voice spike jointly with B. | Stand up FastAPI scaffold. Implement mock tools for Technical Support. Learn Azure Speech / Deepgram APIs. | Voice spike: mic → WS → STT → TTS → speaker. Measure round-trip latency. Scaffold React app. | **M0: Contracts frozen. M1: Voice spike baseline recorded.** |
| **2** | Build LangGraph graph skeleton. Implement `understand` node + `router` node. | Finish Technical Support mock tools. Build YAML workflow loader. Implement step tracker in `executor.py`. | Build UI against fake WS events: transcript view, workflow panel, ticket display. Text input mode. | |
| **3** | Implement `plan`, `policy`, `execute`, `respond` nodes. Wire into full orchestrator loop. Test with text-in. | Build `billing_refund` tool set. Stand up FAISS RAG indexer and seed corpus. | Wire TranscriptPanel to live WS events. Implement WorkflowProgressPanel with real step data. | **M2: Typing "internet is down" → full Technical Support workflow → ticket displayed.** |
| **4** | Add second workflow routing in router node. Build human-handoff summary generator. | Stand up FAISS retriever. Add observability logging per turn (Langfuse). Add `policy_rag` workflow. | Add RAG citations display in TranscriptPanel. UI polish. Lend spare capacity to RAG or mock tools. | |
| **5** | Integrate policy engine into tool-call path. Write policy unit tests. Begin voice merge planning. | Extend mock tools for billing workflow. Finish Langfuse structured logging. Complete RAG routing tests. | Billing/refund workflow UI states. Polish workflow panel. Policy block visual alert. | **M3: Knowledge Q answered with citation; large refund blocked by policy — both visibly distinct.** |
| **6** | Begin voice merge: streaming STT into orchestrator. Streaming TTS out. Measure latency per stage. | Support voice merge from backend. Implement STT webhook handler. Keep latency log per turn. | Client-side voice: mic capture to live backend. Audio playback from streaming TTS. | |
| **7** | Continue latency tuning. Handle unhappy paths: mishears, tool failures, low-confidence intent. | Third workflow mock tools. Begin observability dashboard data API. | End-of-turn UX, "AI thinking" indicator, error states. Barge-in button (stretch). | |
| **8** | Demo scripting. Final latency pass. Buffer for unexpected issues. | Finish observability dashboard. Unhappy-path automated tests. | Demo polish. Presenter-facing controls. Multi-intent UI display. | **M4: Full voice loop within 1.5s budget. M5: All demo checklist items pass on clean run.** |

---

### Latency Budget Validation Steps

At the end of every sprint, run the timing harness:

```python
# backend/tests/test_latency.py
import pytest, asyncio, time
from app.orchestrator.graph import run_turn
from app.state import ConversationState

@pytest.mark.asyncio
async def test_turn_latency():
    """Full orchestrator turn must complete under 1200ms (1.5s budget minus STT + TTS)."""
    state = ConversationState(session_id="test_latency")
    t0 = time.perf_counter()
    state = await run_turn(state, "My internet is down since yesterday")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 1200, f"Turn took {elapsed_ms:.0f}ms — exceeds budget"
```

---

### Testing Strategy by Phase

| Phase | Test Type | Key Test Cases |
|-------|-----------|----------------|
| Phase 0 | **Contract tests** | Tool returns `ToolResult` shape; WS messages match TypeScript types |
| Phase 1 | **Orchestrator unit tests** | `"internet is down"` → Technical Support workflow selected |
| Phase 2 | **Routing tests** | `"What is your refund policy?"` → RAG (not tool); `"refund my money"` → tool |
| Phase 3 | **Policy tests** | Refund > ₹10,000 → blocked; Angry sentiment → escalation |
| Phase 4 | **Latency regression tests** | Per-stage timings logged; any stage > budget triggers alert |
| Phase 5 | **Unhappy path tests** | Mishear → clarification; 3x diagnostic failure → engineer booked; tool failure → escalate |

---

## Section 7 — Demo Execution Checklist & Test Cases {#section-7}

### Setup Script

```bash
#!/bin/bash
# demo-setup.sh — Run before every demo

set -e

echo "🚀 Starting AI Contact Centre demo stack..."

# 1. Bring up infra
docker compose up -d
echo "✅ Redis + PostgreSQL running"

# 2. Wait for health checks
sleep 3

# 3. Seed RAG corpus
cd backend
python -m app.rag.indexer
echo "✅ RAG index built"

# 4. Start backend
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "✅ Backend running (PID: $BACKEND_PID)"

# 5. Start frontend
cd ../frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
echo "✅ Frontend running (PID: $FRONTEND_PID)"

echo ""
echo "🎯 Demo ready at: http://localhost:5173"
echo "📊 API docs at:   http://localhost:8000/docs"
echo ""
echo "Demo accounts:"
echo "  ACC001 — Priya Sharma (Premium tier)"
echo "  ACC002 — Rahul Verma (Standard tier)"
```

---

### Workflow 1: Technical Support Demo Script

```
CUSTOMER: "My internet has been down since yesterday morning and I have a work call soon."

EXPECTED SYSTEM FLOW:
[understand]   → intent: technical_support, sentiment: frustrated, confidence: 0.91
[route]        → workflow: technical_support, step: authenticate
[plan]         → kind: tool, tool: lookup_customer
[policy]       → ALLOW (customer not yet verified — wait, actually verify_unverified triggers here)
[execute]      → lookup_customer() → verified: true, tier: standard
[respond]      → "I've located your account, Priya. Let me check if there's an outage in your area."

[next turn triggers automatically via workflow advance]
[execute]      → check_outage(area_code=MH400001) → outage: false
[respond]      → "No known outages in your area. Let me run a remote diagnostic..."

[execute]      → run_diagnostics() → diagnostic_passed: false, issue: Low SNR
[respond]      → "The diagnostic found a signal issue that we couldn't fix remotely. I'm booking a technician..."

[policy]       → ALLOW (attempts < 3)
[execute]      → book_engineer() → appointment: Tomorrow at 10:00 AM, ref: ENG-ABC123
[execute]      → create_ticket() → INC-10284
[respond]      → "I've booked Raj Kumar for tomorrow at 10 AM (Ref: ENG-ABC123) and raised ticket INC-10284. Is there anything else?"

UI shows: ✅ Customer Identified → ✅ Outage Checked → ✅ Diagnostics Run → ✅ Engineer Booked → 🎫 INC-10284
```

---

### Workflow 2: Billing & Refund Demo Script

```
CUSTOMER: "I was charged twice for last month's bill. I want my money back — ₹2,500."

EXPECTED SYSTEM FLOW:
[understand]   → intent: refund, entities: {amount: 2500}, sentiment: frustrated
[route]        → workflow: billing_refund, step: authenticate
[execute]      → lookup_customer() → verified, ACC001
[execute]      → lookup_invoice() → invoice found, INR 2500 duplicate charge confirmed
[execute]      → check_refund_eligibility() → eligible: true
[policy]       → CHECK refund_payment: amount=2500 < 10000 → ALLOW
[execute]      → refund_payment(amount=2500) → REF-ABCD1234, processing: 3 days
[execute]      → send_sms() → confirmation sent
[execute]      → create_ticket() → INC-20183
[respond]      → "I've processed a refund of ₹2,500 (Ref: REF-ABCD1234) — you'll see it in 3 business days. Ticket INC-20183 raised."

-- POLICY DEMO VARIANT --
CUSTOMER: "I want a refund of ₹15,000 for my last 3 months."
[policy]       → BLOCK: amount > 10,000
UI shows:       🛡️ Policy Gate Active — Manager Approval Required
[respond]      → "This refund of ₹15,000 requires manager approval. I've flagged it and you'll receive confirmation within 24 hours."
```

---

### Workflow 3: Policy RAG Demo Script

```
CUSTOMER: "What is your cancellation policy if I cancel within the first month?"

EXPECTED SYSTEM FLOW:
[understand]   → intent: policy_query, confidence: 0.93, sentiment: neutral
[route]        → workflow: policy_rag, step: classify_query
[plan]         → kind: rag
[policy]       → SKIP (RAG queries bypass policy gate)
[execute]      → retrieve("cancellation policy first month") →
                  [chunk 1: "Customers may cancel within 30 days for a full refund...", source: cancellation_policy.txt, score: 0.94]
                  [chunk 2: "Early termination fees apply after 30 days...", source: cancellation_policy.txt, score: 0.87]
[respond]      → "According to our cancellation policy, you can cancel within the first 30 days for a full refund. After that, early termination fees may apply. [Source: cancellation_policy.txt]"

UI shows:      TranscriptPanel with citation tags: 📄 cancellation_policy.txt (94%)
               Visibly distinct from a tool-based transaction.
```

---

### Edge Case Handlers

```python
# Edge cases the orchestrator must handle

# 1. COMPOUND INTENT
CUSTOMER: "My internet is slow AND I was billed extra this month."
# → Router decomposes: ["billing_refund", "technical_support"]
# → Handles billing first (priority), then technical on next session turn
# → Response: "I see two things to address — let's sort the billing first, then the connection."

# 2. MISHEAR / LOW CONFIDENCE
STT_TRANSCRIPT: "I want to a refun my accound"  # garbled
UNDERSTAND: confidence=0.43
ROUTER: triggers clarification path
RESPONSE: "I want to make sure I get this right — could you rephrase what you need help with?"

# 3. BARGE-IN (stretch goal)
# AI is mid-sentence → customer interrupts
CLIENT → SERVER: { "type": "control", "action": "barge_in" }
# AudioClient.interruptPlayback() clears playback queue
# Backend stops TTS stream, processes new audio from customer

# 4. TOOL FAILURE WITH RETRY
# book_engineer() fails → attempt 1
# book_engineer() fails → attempt 2
# [policy] check_repeated_failures → attempts >= 2 → BLOCK → escalate
# Response: "I'm having difficulty scheduling automatically. Connecting you with a specialist."

# 5. TRIPLE DIAGNOSTIC FAILURE → AUTO-ENGINEER BOOKING
# run_diagnostics() fail × 3
# [policy] _check_diagnostics_threshold → diagnostics_run >= 3 → BLOCK
# Required action: book_engineer()
# [execute] → book_engineer() runs automatically, no LLM decision needed
```

---

### Backend Automated Test Suite Summary

```python
# backend/tests/test_orchestrator.py — Key test cases

ORCHESTRATOR_TEST_CASES = [
    # (input transcript, expected workflow, expected tool called, policy should block)
    ("My internet is down",                      "technical_support", "lookup_customer",  False),
    ("I want a refund of 2500 rupees",           "billing_refund",    "refund_payment",   False),
    ("I want a refund of 15000 rupees",          "billing_refund",    "refund_payment",   True),  # policy blocks
    ("What is your cancellation policy?",        "policy_rag",        None,               False),  # RAG, no tool
    ("My internet slow and billed extra",        "billing_refund",    "lookup_customer",  False),  # compound
    ("I am furious with your terrible service",  "technical_support", None,               True),   # anger escalation
    ("xyzzy blargfoo",                           None,                None,               False),  # low confidence → ask
]
```

---

## Open Questions for Team Review

> [!IMPORTANT]
> **LLM Model Selection**: Confirm `gpt-4o-mini` supports JSON-mode tool-calling reliably. If using a different provider (Anthropic, Google Gemini), the `understand.py`, `plan.py`, and `respond.py` nodes need provider-specific SDK calls. Hide behind a `LLMProvider` abstraction from day one.

> [!IMPORTANT]
> **STT Provider Choice**: Azure Speech has ~150ms endpoint detection. Deepgram Nova-2 is faster (~80ms) but requires WebSocket auth flow. Confirm account availability in Week 1 voice spike before committing.

> [!WARNING]
> **Barge-In**: Scoped as stretch goal. If it becomes a hard requirement, drop Workflow 3 (Policy RAG) from the demo to protect the timeline.

> [!NOTE]
> **WebSocket vs. WebRTC**: The PDF explicitly recommends WebSocket for the single-browser demo. WebRTC has been removed from scope to eliminate the connection-negotiation overhead.
