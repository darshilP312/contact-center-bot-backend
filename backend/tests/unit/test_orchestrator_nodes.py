"""Unit tests for individual orchestrator nodes."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.conversation import ConversationState, CustomerInfo
from app.models.flags import SessionFlags
from app.models.intent import IntentInfo
from app.models.memory import LongTermMemory, WorkingMemory
from app.models.metrics import ObservabilityMetrics
from app.models.workflow import WorkflowState


def make_state(overrides: dict = None) -> dict[str, Any]:
    """Build a minimal AgentState for node testing."""
    session_id = "sess_test"
    state = {
        "session_id": session_id,
        "raw_transcript": "I want to file a claim",
        "pii_masked_transcript": "I want to file a claim",
        "active_language": "en",
        "domain": "insurance",
        "conversation": ConversationState(session_id=session_id, turn_count=1, sentiment="neutral"),
        "customer": CustomerInfo(session_id=session_id, verified=True, customer_id="CUST-001"),
        "intent": IntentInfo(session_id=session_id, name="file_claim", confidence=0.9,
                             entities={"policy_number": "POL-123", "incident_date": "2024-01-15", "incident_type": "car_accident"}),
        "workflow": WorkflowState(session_id=session_id, name="claim_filing", step="authenticate"),
        "flags": SessionFlags(session_id=session_id),
        "working_memory": WorkingMemory(session_id=session_id),
        "long_term_memory": LongTermMemory(session_id=session_id),
        "transcript_history": [],
        "metrics": ObservabilityMetrics(session_id=session_id),
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
        "_ws_connection": None,
        "_domain_loader": None,
        "_tool_registry": None,
        "_rag_node": None,
        "_tts": None,
        "_langfuse": None,
    }
    if overrides:
        state.update(overrides)
    return state


class TestGuardrailsNode:
    @pytest.mark.asyncio
    async def test_pii_masking_phone_number(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        state = make_state({"raw_transcript": "My phone is 9876543210 and I need help"})
        result = await guardrails_node(state)
        assert "9876543210" not in result["pii_masked_transcript"]
        assert "[PHONE_REDACTED]" in result["pii_masked_transcript"]

    @pytest.mark.asyncio
    async def test_frustrated_customer_with_high_turns_escalates(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        conversation = ConversationState(session_id="sess_test", sentiment="frustrated", turn_count=8)
        state = make_state({"conversation": conversation})
        result = await guardrails_node(state)
        assert result["should_escalate"] is True

    @pytest.mark.asyncio
    async def test_neutral_sentiment_no_escalation(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        state = make_state()
        result = await guardrails_node(state)
        assert result["should_escalate"] is False

    @pytest.mark.asyncio
    async def test_urgent_sentiment_escalates(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        conversation = ConversationState(session_id="sess_test", sentiment="urgent", turn_count=2)
        state = make_state({"conversation": conversation})
        result = await guardrails_node(state)
        assert result["should_escalate"] is True

    @pytest.mark.asyncio
    async def test_unverified_customer_transaction_tool_redirected(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        customer = CustomerInfo(session_id="sess_test", verified=False)
        state = make_state({
            "customer": customer,
            "tools_to_call": ["file_claim"],
        })
        result = await guardrails_node(state)
        # Should have been redirected to verify_customer
        assert "GLOBAL_VERIFICATION_001" in result["policy_violations"]
        assert result["tools_to_call"] == ["verify_customer"]

    @pytest.mark.asyncio
    async def test_pii_masking_pan_number(self):
        from app.orchestrator.nodes.guardrails import guardrails_node
        state = make_state({"raw_transcript": "My PAN is ABCDE1234F"})
        result = await guardrails_node(state)
        assert "ABCDE1234F" not in result["pii_masked_transcript"]


class TestWorkflowExecutorNode:
    @pytest.mark.asyncio
    async def test_marks_step_complete(self):
        from app.orchestrator.nodes.workflow_executor import workflow_executor_node

        mock_loader = MagicMock()
        mock_loader.get_workflow = MagicMock(return_value={
            "workflow_id": "claim_filing",
            "workflow_name": "Claim Filing",
            "steps": [
                {"id": "authenticate", "next_step": "verify_policy"},
                {"id": "verify_policy", "next_step": None},
            ],
        })

        state = make_state({
            "_domain_loader": mock_loader,
            "tool_results": [{"tool": "lookup_customer", "status": "success", "result": {"name": "Test"}}],
        })

        result = await workflow_executor_node(state)
        assert "authenticate" in result["workflow"].completed_steps
        assert result["workflow"].step == "verify_policy"

    @pytest.mark.asyncio
    async def test_workflow_complete_when_all_steps_done(self):
        from app.orchestrator.nodes.workflow_executor import workflow_executor_node

        mock_loader = MagicMock()
        mock_loader.get_workflow = MagicMock(return_value={
            "workflow_id": "claim_filing",
            "workflow_name": "Claim Filing",
            "steps": [
                {"id": "authenticate", "next_step": None},
            ],
        })

        state = make_state({"_domain_loader": mock_loader, "tool_results": []})
        result = await workflow_executor_node(state)
        assert "authenticate" in result["workflow"].completed_steps
        assert result["workflow"].step is None  # No more steps


class TestToolCallerNode:
    @pytest.mark.asyncio
    async def test_executes_lookup_customer_tool(self):
        from app.orchestrator.nodes.tool_caller import tool_caller_node
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_register()

        state = make_state({
            "_tool_registry": registry,
            "tools_to_call": ["lookup_customer"],
        })

        result = await tool_caller_node(state)
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool"] == "lookup_customer"
        assert result["tool_results"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_handles_missing_tool_gracefully(self):
        from app.orchestrator.nodes.tool_caller import tool_caller_node
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        state = make_state({
            "_tool_registry": registry,
            "tools_to_call": ["nonexistent_tool"],
        })

        result = await tool_caller_node(state)
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_tool_increments_metrics(self):
        from app.orchestrator.nodes.tool_caller import tool_caller_node
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_register()

        state = make_state({
            "_tool_registry": registry,
            "tools_to_call": ["lookup_customer"],
        })

        initial_count = state["metrics"].tool_calls_made
        result = await tool_caller_node(state)
        assert result["metrics"].tool_calls_made == initial_count + 1

    @pytest.mark.asyncio
    async def test_ticket_flag_set_on_create_ticket(self):
        from app.orchestrator.nodes.tool_caller import tool_caller_node
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_register()

        state = make_state({
            "_tool_registry": registry,
            "tools_to_call": ["create_ticket"],
            "intent": IntentInfo(
                session_id="sess_test",
                name="file_claim",
                confidence=0.9,
                entities={
                    "customer_id": "CUST-001",
                    "intent": "file_claim",
                    "description": "Car accident claim",
                }
            ),
        })

        result = await tool_caller_node(state)
        assert result["flags"].ticket_created is True
