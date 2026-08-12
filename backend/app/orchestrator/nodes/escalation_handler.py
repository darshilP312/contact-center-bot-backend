from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.models.escalation import EscalationSummary
from app.services.llm.client import LLMClient

logger = get_logger("orchestrator.escalation_handler")
_llm = LLMClient()


async def escalation_handler_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Escalation Handler Node — maps to diagram node Q (Human Handoff).

    Responsibilities:
    1. Generate a dense EscalationSummary from all state models
    2. Generate a natural language transcript summary for the human agent
    3. Call route_to_human_agent tool
    4. Update session flags (escalated=True)
    5. Update ConversationState.handoff_summary
    6. Emit session.escalated WebSocket event

    Input:  Full AgentState with should_escalate=True
    Output: state with flags.escalated=True, handoff_summary set
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    tool_registry = state.get("_tool_registry")
    domain = state.get("domain", "insurance")

    conversation = state.get("conversation")
    customer = state.get("customer")
    intent = state.get("intent")
    workflow = state.get("workflow")
    flags = state.get("flags")
    escalation_reason = state.get("escalation_reason", "Customer requested human agent")
    transcript_history = state.get("transcript_history") or []

    logger.info(
        "Escalation handler triggered",
        session_id=session_id,
        node="escalation_handler",
        reason=escalation_reason,
    )

    # Generate transcript summary for human agent
    history_text = "\n".join(
        f"{e.role}: {e.text}" for e in transcript_history[-10:]
    )

    try:
        summary_prompt = f"""Summarize this customer service conversation in 3-4 sentences for a human agent taking over.
Include: what the customer wanted, what was done, why escalation is needed, and any key IDs.

Conversation:
{history_text}

Escalation reason: {escalation_reason}"""

        transcript_summary = await _llm.chat_completion(
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=200,
            session_id=session_id,
            node="escalation_handler",
        )
    except Exception as e:
        logger.error("Failed to generate escalation summary", session_id=session_id, error=str(e))
        transcript_summary = f"Customer contacted regarding {intent.name if intent else 'unknown issue'}. Escalation reason: {escalation_reason}."

    # Build EscalationSummary
    escalation_summary = EscalationSummary(
        session_id=session_id,
        customer_info=customer or __import__("app.models.conversation", fromlist=["CustomerInfo"]).CustomerInfo(session_id=session_id),
        intent=intent or __import__("app.models.intent", fromlist=["IntentInfo"]).IntentInfo(session_id=session_id),
        workflow=workflow or __import__("app.models.workflow", fromlist=["WorkflowState"]).WorkflowState(session_id=session_id),
        flags=flags or __import__("app.models.flags", fromlist=["SessionFlags"]).SessionFlags(session_id=session_id),
        final_sentiment=conversation.sentiment if conversation else "neutral",
        escalation_reason=escalation_reason,
        transcript_summary=transcript_summary,
    )

    # Call route_to_human_agent tool
    handoff_result = None
    if tool_registry:
        handoff_tool = tool_registry.get_tool("route_to_human_agent", domain=domain)
        if handoff_tool:
            try:
                from app.tools.core.handoff import RouteToHumanInput

                handoff_input = RouteToHumanInput(
                    session_id=session_id,
                    customer_id=customer.customer_id if customer and customer.customer_id else None,
                    escalation_reason=escalation_reason,
                    final_sentiment=conversation.sentiment if conversation else "neutral",
                    transcript_summary=transcript_summary,
                    priority="high" if (conversation and conversation.sentiment in ("frustrated", "urgent")) else "normal",
                )
                handoff_result = await handoff_tool.execute(handoff_input)
            except Exception as e:
                logger.error(
                    "route_to_human_agent failed",
                    session_id=session_id,
                    node="escalation_handler",
                    error=str(e),
                )

    # Update state
    if flags:
        flags.escalated = True

    if conversation:
        conversation.handoff_summary = transcript_summary

    # Emit WebSocket event
    if ws:
        payload = escalation_summary.model_dump(mode="json")
        if handoff_result:
            payload["handoff"] = handoff_result.model_dump(mode="json")
        await ws.send_json("session.escalated", payload)

        # Final agent message
        wait_time = handoff_result.estimated_wait_minutes if handoff_result else 5
        queue_pos = handoff_result.queue_position if handoff_result else 1
        await ws.send_json(
            "response.text",
            {
                "text": (
                    f"I'm connecting you to a human agent who can better assist you. "
                    f"You're #{queue_pos} in the queue with an estimated wait of {wait_time} minutes. "
                    f"I've shared our full conversation history with the agent so you won't need to repeat yourself."
                ),
                "is_final": True,
                "rag_used": False,
                "session_id": session_id,
            },
        )

    logger.info(
        "Escalation completed",
        session_id=session_id,
        node="escalation_handler",
        handoff_id=handoff_result.handoff_id if handoff_result else None,
    )

    return state
