from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.conversation import ConversationState, CustomerInfo
from app.models.flags import SessionFlags
from app.models.intent import IntentInfo
from app.models.memory import LongTermMemory, WorkingMemory
from app.models.metrics import ObservabilityMetrics
from app.models.transcript import TranscriptEntry
from app.models.workflow import WorkflowState


@pytest.fixture
def session_id() -> str:
    return "sess_test123"


@pytest.fixture
def sample_conversation(session_id) -> ConversationState:
    return ConversationState(session_id=session_id, turn_count=2, sentiment="neutral")


@pytest.fixture
def sample_customer(session_id) -> CustomerInfo:
    return CustomerInfo(
        session_id=session_id,
        verified=True,
        customer_id="CUST-123",
        name="Test User",
        tier="premium",
    )


@pytest.fixture
def sample_intent(session_id) -> IntentInfo:
    return IntentInfo(
        session_id=session_id,
        name="file_claim",
        confidence=0.92,
        entities={"policy_number": "POL-ABC123", "incident_date": "2024-01-15", "incident_type": "car_accident"},
    )


@pytest.fixture
def sample_workflow(session_id) -> WorkflowState:
    return WorkflowState(session_id=session_id, name="claim_filing", step="authenticate")


@pytest.fixture
def sample_flags(session_id) -> SessionFlags:
    return SessionFlags(session_id=session_id)


@pytest.fixture
def sample_metrics(session_id) -> ObservabilityMetrics:
    return ObservabilityMetrics(session_id=session_id)


@pytest.fixture
def sample_agent_state(
    session_id,
    sample_conversation,
    sample_customer,
    sample_intent,
    sample_workflow,
    sample_flags,
    sample_metrics,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "raw_transcript": "I want to file a claim for my car accident",
        "pii_masked_transcript": "I want to file a claim for my car accident",
        "active_language": "en",
        "domain": "insurance",
        "conversation": sample_conversation,
        "customer": sample_customer,
        "intent": sample_intent,
        "workflow": sample_workflow,
        "flags": sample_flags,
        "working_memory": WorkingMemory(session_id=session_id),
        "long_term_memory": LongTermMemory(session_id=session_id),
        "transcript_history": [],
        "metrics": sample_metrics,
        "missing_entities": [],
        "requires_rag": False,
        "tools_to_call": [],
        "clarification_needed": False,
        "clarification_question": None,
        "policy_violations": [],
        "should_escalate": False,
        "escalation_reason": None,
        "tool_results": [],
        "rag_result": None,
        "rag_citations": [],
        "response_text": "",
        "response_audio_queued": False,
        "next_node": None,
        "loop_count": 0,
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock(return_value=True)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.lpush = AsyncMock(return_value=1)
    redis.ltrim = AsyncMock(return_value=True)
    redis.pipeline = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            hset=AsyncMock(), expire=AsyncMock(), execute=AsyncMock(return_value=[True, True])
        )),
        __aexit__=AsyncMock(return_value=None),
    ))
    return redis


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = AsyncMock()
    client.chat_completion = AsyncMock(return_value="I can help you with that claim.")
    client.structured_completion = AsyncMock(return_value={
        "intent_name": "file_claim",
        "confidence": 0.92,
        "entities": {"policy_number": "POL-123"},
        "secondary_intents": [],
        "sentiment": "neutral",
    })
    return client


@pytest.fixture
def mock_domain_loader():
    """Mock domain loader with insurance domain."""
    loader = MagicMock()
    loader.domains = {
        "insurance": {
            "domain_id": "insurance",
            "domain_name": "Insurance",
            "version": "1.0.0",
            "intents": [
                {
                    "name": "file_claim",
                    "description": "File a new claim",
                    "required_entities": ["policy_number", "incident_date", "incident_type"],
                    "optional_entities": ["damage_amount"],
                    "maps_to_workflow": "claim_filing",
                    "maps_to_tools": ["lookup_policy", "file_claim"],
                    "requires_rag": False,
                }
            ],
            "enabled_tools": ["lookup_customer", "verify_customer", "file_claim", "lookup_policy"],
            "escalation_config": {"max_turns": 10},
        }
    }
    loader.get_domain = MagicMock(return_value=loader.domains["insurance"])
    loader.get_intent = MagicMock(return_value=loader.domains["insurance"]["intents"][0])
    loader.get_intent_taxonomy = MagicMock(return_value=loader.domains["insurance"]["intents"])
    loader.get_workflow = MagicMock(return_value={
        "workflow_id": "claim_filing",
        "workflow_name": "Claim Filing",
        "steps": [
            {"id": "authenticate", "next_step": "verify_policy", "required_tools": ["lookup_customer"]},
            {"id": "verify_policy", "next_step": "collect_details", "required_tools": ["lookup_policy"]},
        ],
    })
    loader.get_knowledge_dir = MagicMock(return_value=None)
    return loader
