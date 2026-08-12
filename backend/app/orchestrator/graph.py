"""
graph.py — LangGraph Orchestrator: the complete 6-node execution graph.
Build once at startup; invoke once per conversational turn.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Literal, Optional

from langgraph.graph import StateGraph, END

from app.state import ConversationState
from app.orchestrator.nodes import understand, router, plan, policy, execute, respond
from app.telemetry import log_turn_complete

logger = logging.getLogger("cc.orchestrator")


# ─── Edge routing functions ───────────────────────────────────────────────────

def _after_plan(state: dict) -> Literal["policy", "execute"]:
    """Tool calls go through policy gate; everything else goes straight to execute."""
    action_kind = state.get("planned_action", {}).get("kind", "ask")
    return "policy" if action_kind == "tool" else "execute"


def _after_policy(state: dict) -> Literal["execute", "respond"]:
    """If policy blocked the action, skip to respond (pre-canned message). Else execute."""
    verdict = state.get("policy_verdict", {})
    # After policy blocks, planned_action is replaced with a message-bearing action
    # We still need to execute (e.g. for forced tool calls) or go to respond
    new_action = state.get("planned_action", {})
    new_kind = new_action.get("kind", "ask")

    if verdict.get("blocked") and new_kind in ("await_approval", "escalate", "ask"):
        return "respond"  # Skip execution, use pre-canned message
    return "execute"


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """Build and compile the LangGraph state machine."""
    builder = StateGraph(dict)

    builder.add_node("understand", understand.node)
    builder.add_node("route",     router.node)
    builder.add_node("plan",      plan.node)
    builder.add_node("policy",    policy.node)
    builder.add_node("execute",   execute.node)
    builder.add_node("respond",   respond.node)

    builder.set_entry_point("understand")

    builder.add_edge("understand", "route")
    builder.add_edge("route",      "plan")

    builder.add_conditional_edges(
        "plan",
        _after_plan,
        {"policy": "policy", "execute": "execute"},
    )

    builder.add_conditional_edges(
        "policy",
        _after_policy,
        {"execute": "execute", "respond": "respond"},
    )

    builder.add_edge("execute", "respond")
    builder.add_edge("respond", END)

    return builder.compile()


# ── Singleton compiled graph ───────────────────────────────────────────────────
_graph = build_graph()


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_turn(
    conversation_state: ConversationState,
    transcript: str,
    stream_callback: Optional[Callable] = None,
) -> ConversationState:
    """
    Execute one complete orchestrator turn.

    Args:
        conversation_state: Current session state (loaded from Redis).
        transcript:         Final STT transcript for this turn.
        stream_callback:    Async callable(token: str) for streaming TTS.

    Returns:
        Updated ConversationState to persist back to Redis.
    """
    input_dict = {
        "state": conversation_state.to_dict(),
        "transcript_text": transcript,
        "stream_callback": stream_callback,
        "planned_action": None,
        "policy_verdict": None,
        "execution_result": None,
        "generated_reply": None,
        "reply_citations": [],
        "ticket_id": None,
    }

    try:
        result = await _graph.ainvoke(input_dict)
    except Exception as e:
        logger.error(f"Orchestrator graph failed: {e}", exc_info=True)
        result = input_dict
        result["generated_reply"] = (
            "I'm sorry, I encountered an internal error. "
            "Let me connect you with a specialist."
        )

    # Reconstruct updated state
    updated_state = ConversationState.from_dict(result["state"])
    updated_state.turn_count += 1

    # Emit observability
    obs = log_turn_complete(
        session_id=updated_state.session_id,
        turn_count=updated_state.turn_count,
        intent=updated_state.intent.name,
        workflow=updated_state.workflow.name,
        step=updated_state.workflow.step,
        tool_calls=updated_state.metrics.tool_calls_made[-5:],  # last 5
        policy_blocked=result.get("policy_verdict", {}) is not None
            and result.get("policy_verdict", {}).get("blocked", False),
        total_tokens=updated_state.metrics.total_tokens_used,
        cost_usd=updated_state.metrics.total_cost_usd,
    )

    # Attach observability to result for websocket push
    result["observability_event"] = obs
    result["_updated_state"] = updated_state

    return updated_state, result
