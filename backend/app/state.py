"""
state.py — ConversationState: the single source of truth for every session.
Stored in Redis. Read and written by every orchestrator component.
Schema changes here must be reflected in .agents/brain.md and .agents/summary.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Sub-models ──────────────────────────────────────────────────────────────

class CustomerInfo(BaseModel):
    """Identity and verification status of the caller."""
    verified: bool = False
    customer_id: Optional[str] = None
    name: Optional[str] = None
    tier: Optional[Literal["standard", "premium"]] = None
    phone: Optional[str] = None
    account_no: Optional[str] = None
    email: Optional[str] = None
    area_code: Optional[str] = None


class IntentInfo(BaseModel):
    """Extracted intent, confidence, entities, and compound intents."""
    name: Optional[str] = None
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)
    secondary_intents: list[str] = Field(default_factory=list)


class WorkflowState(BaseModel):
    """Active workflow execution state."""
    name: Optional[str] = None
    step: Optional[str] = None
    completed_steps: list[str] = Field(default_factory=list)
    step_attempts: dict[str, int] = Field(default_factory=dict)
    step_results: dict[str, Any] = Field(default_factory=dict)


class SessionFlags(BaseModel):
    """Boolean flags tracking key events in the session."""
    ticket_created: bool = False
    engineer_booked: bool = False
    escalated: bool = False
    awaiting_approval: bool = False
    refund_triggered: bool = False
    rag_used: bool = False
    barge_in_detected: bool = False


class TranscriptEntry(BaseModel):
    """A single turn entry in the conversation transcript."""
    role: Literal["user", "assistant", "system"]
    text: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rag_citations: list[str] = Field(default_factory=list)


class WorkingMemory(BaseModel):
    """Short-lived facts about the current workflow execution."""
    current_workflow: Optional[str] = None
    router_restarted: bool = False
    diagnostics_run: int = 0
    last_tool_result: Optional[dict] = None
    pending_action: Optional[str] = None
    intent_queue: list[str] = Field(default_factory=list)


class LongTermMemory(BaseModel):
    """Persisted facts from previous sessions — loaded from Postgres on start."""
    previous_tickets: list[str] = Field(default_factory=list)
    last_call_date: Optional[datetime] = None
    engineer_visit_history: list[str] = Field(default_factory=list)
    known_issues: list[str] = Field(default_factory=list)


class ObservabilityMetrics(BaseModel):
    """Per-session observability counters — flushed to Langfuse per turn."""
    turn_latencies_ms: list[dict[str, float]] = Field(default_factory=list)
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    tool_calls_made: list[str] = Field(default_factory=list)
    policy_blocks: int = 0


# ─── Root State ───────────────────────────────────────────────────────────────

class ConversationState(BaseModel):
    """
    The spine of the system.
    One object per session, held in Redis.
    Every component reads and writes it; it is the single source of truth.
    """

    session_id: str = Field(
        default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    channel: Literal["voice", "text", "web"] = "voice"

    customer: CustomerInfo = Field(default_factory=CustomerInfo)
    intent: IntentInfo = Field(default_factory=IntentInfo)
    workflow: WorkflowState = Field(default_factory=WorkflowState)
    flags: SessionFlags = Field(default_factory=SessionFlags)

    sentiment: Literal["neutral", "frustrated", "angry", "satisfied"] = "neutral"
    turn_count: int = 0

    working_memory: WorkingMemory = Field(default_factory=WorkingMemory)
    long_term_memory: LongTermMemory = Field(default_factory=LongTermMemory)
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    metrics: ObservabilityMetrics = Field(default_factory=ObservabilityMetrics)

    handoff_summary: Optional[str] = None
    ticket_id: Optional[str] = None

    class Config:
        use_enum_values = True

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_redis(self) -> str:
        """Serialise for Redis storage."""
        return self.model_dump_json()

    @classmethod
    def from_redis(cls, raw: str) -> "ConversationState":
        """Deserialise from Redis JSON string."""
        return cls.model_validate_json(raw)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def add_transcript(
        self,
        role: str,
        text: str,
        citations: Optional[list[str]] = None,
    ) -> None:
        """Append a turn to the conversation transcript."""
        self.transcript.append(TranscriptEntry(
            role=role,
            text=text,
            rag_citations=citations or [],
        ))

    def advance_workflow_step(
        self,
        next_step: str,
        result: Optional[dict] = None,
    ) -> None:
        """Mark current step completed and advance to next_step."""
        if self.workflow.step:
            if self.workflow.step not in self.workflow.completed_steps:
                self.workflow.completed_steps.append(self.workflow.step)
            if result:
                self.workflow.step_results[self.workflow.step] = result
        self.workflow.step = next_step

    def increment_step_attempt(self) -> int:
        """Increment and return the attempt count for the current step."""
        step = self.workflow.step or "__unknown__"
        self.workflow.step_attempts[step] = (
            self.workflow.step_attempts.get(step, 0) + 1
        )
        return self.workflow.step_attempts[step]

    def to_dict(self) -> dict:
        """Convert to plain dict for LangGraph node passing."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationState":
        """Reconstruct from plain dict."""
        return cls.model_validate(d)
