from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.models.conversation import ConversationState, CustomerInfo
from app.models.flags import SessionFlags
from app.models.intent import IntentInfo
from app.models.memory import LongTermMemory, WorkingMemory
from app.models.metrics import ObservabilityMetrics
from app.models.transcript import TranscriptEntry
from app.models.workflow import WorkflowState


class AgentState(TypedDict, total=False):
    """
    LangGraph AgentState — the single source of truth passed between all nodes.

    All nodes read from and write to this state. LangGraph merges node outputs
    back into this dict automatically. The `total=False` allows partial updates
    from each node.
    """

    # ── Input for this turn ──────────────────────────────────────────────────
    session_id: str
    raw_transcript: str                        # Current turn raw text from STT
    pii_masked_transcript: str                 # PII-scrubbed version (used in prompts)
    active_language: str                       # ISO 639-1 code, e.g. "en", "hi"
    domain: str                                # Active domain plugin, e.g. "insurance"

    # ── Conversation state tables ────────────────────────────────────────────
    conversation: ConversationState
    customer: CustomerInfo
    intent: IntentInfo
    workflow: WorkflowState
    flags: SessionFlags
    working_memory: WorkingMemory
    long_term_memory: LongTermMemory
    transcript_history: List[TranscriptEntry]  # Last N turns (STM)
    metrics: ObservabilityMetrics

    # ── Planner outputs ──────────────────────────────────────────────────────
    intent_type: str                           # INFORMATIONAL_RAG | ACTIONAL_WORKFLOW | DIAGNOSTIC_ACTION
    missing_entities: List[str]                # Entities needed before proceeding
    requires_rag: bool
    tools_to_call: List[str]
    clarification_needed: bool
    clarification_question: Optional[str]
    policy_evaluations: List[Dict[str, Any]]   # Per-rule evaluation log from planner

    # ── Business rule inputs ─────────────────────────────────────────────────
    failed_diagnostics_count: int              # Number of failed diagnostic attempts this session
    refund_amount: Optional[float]             # Requested refund amount (INR) for monetary gate
    manager_approval_required: bool            # True when refund >= INR 10,000

    # ── Policy & guardrails ──────────────────────────────────────────────────
    policy_violations: List[str]
    should_escalate: bool
    escalation_reason: Optional[str]

    # ── Execution results ────────────────────────────────────────────────────
    tool_results: List[Dict[str, Any]]
    rag_result: Optional[str]
    rag_citations: List[str]

    # ── Response ─────────────────────────────────────────────────────────────
    response_text: str
    response_audio_queued: bool

    # ── Graph control ────────────────────────────────────────────────────────
    next_node: Optional[str]
    loop_count: int                            # Prevents infinite planner loops

    # ── Runtime references (not serialised to Redis) ─────────────────────────
    _ws_connection: Any                        # WebSocket connection for events
    _domain_loader: Any                        # DomainLoader instance
    _tool_registry: Any                        # ToolRegistry instance
    _rag_node: Any                             # RAGNode instance
    _tts: Any                                  # TTS provider
    _langfuse: Any                             # Langfuse client


async def build_initial_state(
    session_id: str,
    raw_transcript: str,
    domain: str,
    language: str,
    session_data: Optional[Dict[str, Any]],
    redis: Any,
) -> AgentState:
    """
    Build an AgentState from a Redis session snapshot and current transcript.

    Args:
        session_id: Session ID.
        raw_transcript: The current turn's STT/text input.
        domain: Active domain plugin ID.
        language: Active language code.
        session_data: Raw session dict from Redis (or None for new sessions).
        redis: Redis client for STM history loading.

    Returns:
        Populated AgentState ready for graph invocation.
    """
    from app.orchestrator.memory.short_term import ShortTermMemory

    if session_data is None:
        session_data = {}

    def _get(key: str, model_class, defaults: Dict[str, Any] | None = None) -> Any:
        raw = session_data.get(key, {})
        if isinstance(raw, dict):
            return model_class(**{**raw, "session_id": session_id})
        return model_class(session_id=session_id, **(defaults or {}))

    # Load transcript history from Redis STM
    stm = ShortTermMemory(redis)
    history = await stm.get_history(session_id, n=10)

    customer = _get("customer", CustomerInfo)
    if not customer.customer_id:
        customer.customer_id = "CUST-1001"
        customer.name = "Priya Patel"
        customer.tier = "premium"
        customer.verified = True
        customer.phone = "+91-9876543210"
        customer.account_no = "ACC-9876-1234"

    state: AgentState = {
        "session_id": session_id,
        "raw_transcript": raw_transcript,
        "pii_masked_transcript": raw_transcript,  # Guardrails will mask this
        "active_language": language,
        "domain": domain,
        "conversation": _get("conversation", ConversationState),
        "customer": customer,
        "intent": _get("intent", IntentInfo),
        "workflow": _get("workflow", WorkflowState),
        "flags": _get("flags", SessionFlags),
        "working_memory": _get("working_memory", WorkingMemory),
        "long_term_memory": _get("long_term_memory", LongTermMemory),
        "transcript_history": history,
        "metrics": _get("metrics", ObservabilityMetrics),
        # Planner / Decision Engine defaults
        "intent_type": "ACTIONAL_WORKFLOW",    # Default; overridden each turn by planner
        "missing_entities": [],
        "requires_rag": False,
        "tools_to_call": [],
        "clarification_needed": False,
        "clarification_question": None,
        "policy_evaluations": [],              # Per-rule evaluation log populated by planner
        # Business rule state
        "failed_diagnostics_count": int(session_data.get("failed_diagnostics_count", 0)),
        "refund_amount": session_data.get("refund_amount"),
        "manager_approval_required": bool(session_data.get("manager_approval_required", False)),
        # Policy defaults
        "policy_violations": [],
        "should_escalate": False,
        "escalation_reason": None,
        # Execution defaults
        "tool_results": [],
        "rag_result": None,
        "rag_citations": [],
        # Response defaults
        "response_text": "",
        "response_audio_queued": False,
        # Graph control
        "next_node": None,
        "loop_count": 0,
    }

    return state
