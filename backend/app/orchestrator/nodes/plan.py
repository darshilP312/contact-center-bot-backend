"""
plan.py — Node 3: PLAN
Decide the next action: tool call, RAG retrieval, clarification, or escalation.
LLM call #2 per turn. Uses structured context — never raw conversation history.
"""

from __future__ import annotations

import json
import logging
import time

from openai import AsyncOpenAI

from app.config import settings
from app.orchestrator.prompts import PLAN_PROMPT
from app.telemetry import log_stage
from app.workflows.loader import load_workflow

logger = logging.getLogger("cc.node.plan")
client = AsyncOpenAI(api_key=settings.openai_api_key)


async def node(state: dict) -> dict:
    """
    Given the current workflow step, decide the next action.
    Short-circuits to RAG if the step action is 'rag'.
    """
    t0 = time.perf_counter()
    conv_state = state["state"]

    # If the router already set a planned_action (e.g. clarification), skip planning
    if state.get("planned_action"):
        return state

    workflow_name = conv_state.get("workflow", {}).get("name")
    current_step = conv_state.get("workflow", {}).get("step")

    # ── Short-circuit: no active workflow ─────────────────────────────────────
    if not workflow_name or not current_step:
        state["planned_action"] = {
            "kind": "ask",
            "ask_text": "How can I help you today?",
            "reasoning": "No active workflow.",
        }
        return state

    # ── Load step definition ──────────────────────────────────────────────────
    try:
        wf = load_workflow(workflow_name)
        step_def = wf.get_step(current_step)
    except Exception as e:
        logger.error(f"Failed to load workflow step: {e}")
        step_def = None

    # ── Short-circuit: RAG action ─────────────────────────────────────────────
    if step_def and step_def.action in ("rag", "rag_classify"):
        query = _build_rag_query(step_def, conv_state)
        state["planned_action"] = {
            "kind": "rag",
            "rag_query": query,
            "rag_top_k": step_def.rag_top_k,
            "reasoning": "Step action is RAG retrieval.",
        }
        log_stage("plan", (time.perf_counter() - t0) * 1000)
        return state

    # ── LLM planning call ─────────────────────────────────────────────────────
    step_goal = step_def.goal if step_def else "Complete the current step."
    available_tool = step_def.tool if step_def else None
    entities = conv_state.get("intent", {}).get("entities", {})
    customer = conv_state.get("customer", {})

    prompt = PLAN_PROMPT.format(
        intent_name=conv_state.get("intent", {}).get("name", "unknown"),
        confidence=conv_state.get("intent", {}).get("confidence", 0.0),
        workflow_name=workflow_name,
        current_step=current_step,
        step_goal=step_goal,
        customer_verified=customer.get("verified", False),
        sentiment=conv_state.get("sentiment", "neutral"),
        flags=json.dumps(conv_state.get("flags", {})),
        last_tool_result=json.dumps(
            conv_state.get("working_memory", {}).get("last_tool_result", {})
        )[:300],
        available_tool=available_tool or "none",
        customer_id=customer.get("customer_id") or "unknown",
        account_no=customer.get("account_no") or entities.get("account_no") or "unknown",
        area_code=customer.get("area_code") or entities.get("area_code") or "unknown",
        amount=entities.get("amount") or 0,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.plan_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        planned = json.loads(response.choices[0].message.content)
        tokens = response.usage.total_tokens if response.usage else 0
    except Exception as e:
        logger.error(f"plan node LLM call failed: {e}")
        planned = {
            "kind": "ask",
            "ask_text": "I'm having a moment of difficulty. Could you please repeat that?",
            "reasoning": f"LLM error: {e}",
        }
        tokens = 0

    conv_state["metrics"]["total_tokens_used"] += tokens

    # Inject override args from workflow YAML if present
    if step_def and step_def.tool_args_override and planned.get("kind") == "tool":
        planned["tool_args"] = {
            **planned.get("tool_args", {}),
            **step_def.tool_args_override,
        }

    state["planned_action"] = planned
    state["state"] = conv_state

    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("plan", latency_ms, tokens=tokens)
    logger.info(f"plan: kind={planned.get('kind')} tool={planned.get('tool_name')} reason={planned.get('reasoning')}")

    return state


def _build_rag_query(step_def, conv_state: dict) -> str:
    """Build a RAG query from the step template and current state entities."""
    template = step_def.rag_query_template or "{intent}"
    entities = conv_state.get("intent", {}).get("entities", {})
    intent = conv_state.get("intent", {}).get("name", "")
    return template.format(
        reason=entities.get("reason", ""),
        intent=intent,
        account_no=conv_state.get("customer", {}).get("account_no", ""),
    )
