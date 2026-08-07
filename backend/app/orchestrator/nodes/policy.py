"""
policy.py — Node 4: POLICY GATE
Deterministic evaluation of business rules before any tool executes.
The LLM is NEVER consulted here. Rules are checked in priority order.
"""

from __future__ import annotations

import logging

from app.policies.engine import PolicyEngine

logger = logging.getLogger("cc.node.policy")
_engine = PolicyEngine()


async def node(state: dict) -> dict:
    """
    Evaluate policy rules against the planned action and current state.
    If blocked, replaces the planned action with the required alternative.
    """
    conv_state = state["state"]
    planned_action = state.get("planned_action", {})

    # Policy only applies to tool calls
    if planned_action.get("kind") != "tool":
        state["policy_verdict"] = {"blocked": False, "reason": "", "required_action": None}
        return state

    verdict = _engine.evaluate(planned_action, conv_state)
    state["policy_verdict"] = verdict

    if verdict["blocked"]:
        logger.warning(
            f"POLICY BLOCK: {verdict['reason']} | "
            f"action={planned_action.get('tool_name')} | "
            f"required={verdict['required_action'].get('kind')}"
        )

        # Replace planned action with the policy-required alternative
        state["planned_action"] = verdict["required_action"]

        # Update flags
        flags = conv_state.get("flags", {})
        required_kind = verdict["required_action"].get("kind", "")
        if required_kind == "await_approval":
            flags["awaiting_approval"] = True
        elif required_kind == "escalate":
            flags["escalated"] = True
        conv_state["flags"] = flags
        conv_state["metrics"]["policy_blocks"] = (
            conv_state["metrics"].get("policy_blocks", 0) + 1
        )
    else:
        logger.debug(f"Policy ALLOW: tool={planned_action.get('tool_name')}")

    state["state"] = conv_state
    return state
