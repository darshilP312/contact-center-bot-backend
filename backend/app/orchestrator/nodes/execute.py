"""
execute.py — Node 5: EXECUTE
Dispatch the planned action to a mock tool or RAG retriever.
Applies the result to the conversation state via the workflow executor.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from typing import Callable, Optional

from app.rag.retriever import retrieve
from app.workflows.executor import advance_workflow
from app.telemetry import log_stage

logger = logging.getLogger("cc.node.execute")


async def node(state: dict) -> dict:
    """
    Execute the planned action and update state with the result.
    Handles: tool calls, RAG retrieval, clarification, escalation.
    """
    t0 = time.perf_counter()
    conv_state = state["state"]
    action = state.get("planned_action", {})
    kind = action.get("kind", "ask")

    # ── TOOL CALL ─────────────────────────────────────────────────────────────
    if kind == "tool":
        tool_name = action.get("tool_name", "")
        tool_args = dict(action.get("tool_args", {}))

        # Inject session context that tools may need
        tool_args.setdefault("customer_id", conv_state["customer"].get("customer_id"))
        tool_args.setdefault("session_id", conv_state.get("session_id"))

        tool_result = await _call_tool(tool_name, tool_args)
        state["execution_result"] = {
            "kind": "tool",
            "tool": tool_name,
            "result": tool_result,
        }

        # Track in working memory and metrics
        conv_state["working_memory"]["last_tool_result"] = tool_result
        calls_made = conv_state["metrics"].get("tool_calls_made", [])
        calls_made.append(tool_name)
        conv_state["metrics"]["tool_calls_made"] = calls_made

        # Track diagnostics run count
        if tool_name == "run_diagnostics":
            wm = conv_state.get("working_memory", {})
            wm["diagnostics_run"] = wm.get("diagnostics_run", 0) + 1
            conv_state["working_memory"] = wm

        # Update customer info from lookup result
        if tool_name == "lookup_customer" and tool_result.get("ok"):
            data = tool_result["data"]
            conv_state["customer"].update({
                "verified": data.get("verified", False),
                "customer_id": data.get("customer_id"),
                "name": data.get("name"),
                "tier": data.get("tier"),
                "phone": data.get("phone"),
                "area_code": data.get("area_code"),
                "email": data.get("email"),
                "account_no": data.get("account_no"),
            })

        # Advance workflow based on result
        conv_state = advance_workflow(conv_state, tool_result)

    # ── RAG RETRIEVAL ─────────────────────────────────────────────────────────
    elif kind == "rag":
        query = action.get("rag_query", "")
        top_k = action.get("rag_top_k", 3)
        rag_result = await retrieve(query, top_k=top_k)
        state["execution_result"] = {"kind": "rag", "result": rag_result}
        conv_state["flags"]["rag_used"] = True

    # ── CLARIFICATION ─────────────────────────────────────────────────────────
    elif kind == "ask":
        state["execution_result"] = {
            "kind": "ask",
            "text": action.get("ask_text", "Could you please provide more information?"),
        }

    # ── ESCALATION / AWAIT APPROVAL ───────────────────────────────────────────
    elif kind in ("escalate", "await_approval"):
        summary = _build_handoff_summary(conv_state)
        conv_state["handoff_summary"] = summary
        conv_state["flags"]["escalated"] = True
        state["execution_result"] = {
            "kind": kind,
            "summary": summary,
            "message": action.get("message", ""),
        }

    else:
        logger.warning(f"Unknown action kind: {kind}")
        state["execution_result"] = {"kind": "unknown"}

    state["state"] = conv_state
    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("execute", latency_ms)

    logger.info(
        f"execute: kind={kind} "
        f"result_ok={state['execution_result'].get('result', {}).get('ok', 'N/A')}"
    )
    return state


async def _call_tool(tool_name: str, args: dict) -> dict:
    """Dynamically load and invoke a tool by name. Catches all exceptions."""
    try:
        module = importlib.import_module(f"app.tools.{tool_name}")
        func = getattr(module, tool_name)

        if asyncio.iscoroutinefunction(func):
            return await func(**args)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(**args))

    except ModuleNotFoundError:
        logger.error(f"Tool not found: app.tools.{tool_name}")
        return {"ok": False, "data": {}, "error": f"Tool '{tool_name}' not found."}
    except Exception as e:
        logger.error(f"Tool '{tool_name}' raised exception: {e}", exc_info=True)
        return {"ok": False, "data": {}, "error": str(e)}


def _build_handoff_summary(state: dict) -> str:
    """Generate a human-agent-ready handoff summary from the current state."""
    customer = state.get("customer", {})
    workflow = state.get("workflow", {})
    return (
        f"Customer: {customer.get('name', 'Unknown')} "
        f"(ID: {customer.get('customer_id', 'N/A')}, "
        f"Tier: {customer.get('tier', 'standard')})\n"
        f"Verified: {customer.get('verified', False)}\n"
        f"Intent: {state.get('intent', {}).get('name', 'unknown')}\n"
        f"Workflow: {workflow.get('name', 'N/A')}, "
        f"Step: {workflow.get('step', 'N/A')}\n"
        f"Completed steps: {', '.join(workflow.get('completed_steps', []))}\n"
        f"Sentiment: {state.get('sentiment', 'neutral')}\n"
        f"Ticket: {state.get('ticket_id', 'Not created')}\n"
        f"Flags: {state.get('flags', {})}"
    )
