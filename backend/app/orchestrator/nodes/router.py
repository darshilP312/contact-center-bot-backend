"""
router.py — Node 2: ROUTE
Deterministic routing: selects workflow, handles compound intents, low confidence.
NO LLM call in this node — all routing is rule-based.
"""

from __future__ import annotations

import logging

from app.workflows.loader import load_workflow

logger = logging.getLogger("cc.node.router")

CONFIDENCE_THRESHOLD = 0.65

INTENT_TO_WORKFLOW: dict[str, str] = {
    "technical_support": "technical_support",
    "billing":           "billing_refund",
    "refund":            "billing_refund",
    "policy_query":      "policy_rag",
    "complaint":         "technical_support",
    "password_reset":    "technical_support",
    "general":           "policy_rag",
}

INTENT_PRIORITY: list[str] = [
    "billing", "refund", "technical_support", "complaint",
    "policy_query", "password_reset", "general",
]


async def node(state: dict) -> dict:
    """
    Route the conversation to the appropriate workflow.
    Handle compound intents by decomposing and prioritising them.
    """
    conv_state = state["state"]
    intent = conv_state.get("intent", {})

    # ── 1. Low confidence → ask for clarification ─────────────────────────────
    if intent.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        logger.info(f"Low confidence ({intent.get('confidence'):.2f}) — requesting clarification")
        state["planned_action"] = {
            "kind": "ask",
            "ask_text": (
                "I want to make sure I help you with the right thing. "
                "Could you tell me a bit more about what you need today?"
            ),
            "reasoning": "Confidence below threshold.",
        }
        state["state"] = conv_state
        return state

    # ── 2. Compound intent decomposition ─────────────────────────────────────
    all_intents = [intent.get("name", "unknown")] + intent.get("secondary_intents", [])
    all_intents = [i for i in all_intents if i and i != "unknown"]

    if len(all_intents) > 1:
        # Sort by priority; handle primary intent first
        sorted_intents = sorted(
            all_intents,
            key=lambda i: INTENT_PRIORITY.index(i) if i in INTENT_PRIORITY else 99,
        )
        conv_state["working_memory"]["intent_queue"] = sorted_intents[1:]
        primary = sorted_intents[0]
        conv_state["intent"]["name"] = primary
        logger.info(f"Compound intent: primary={primary}, queued={sorted_intents[1:]}")

    # ── 3. Select workflow if none is active ──────────────────────────────────
    if not conv_state.get("workflow", {}).get("name"):
        intent_name = conv_state["intent"].get("name", "unknown")
        workflow_name = INTENT_TO_WORKFLOW.get(intent_name)

        if workflow_name:
            try:
                wf = load_workflow(workflow_name)
                conv_state["workflow"]["name"] = wf.name
                conv_state["workflow"]["step"] = wf.entry_step
                logger.info(f"Workflow selected: {wf.name}, starting at: {wf.entry_step}")
            except FileNotFoundError as e:
                logger.error(f"Workflow not found: {e}")
        else:
            logger.warning(f"No workflow mapped for intent: {intent_name}")

    state["state"] = conv_state
    return state
