"""
respond.py — Node 6: RESPOND
Generate a concise, empathetic, TTS-optimised reply from structured context.
LLM call #3 per turn. Streams tokens via callback for low-latency TTS.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.orchestrator.prompts import RESPOND_PROMPT
from app.telemetry import log_stage

logger = logging.getLogger("cc.node.respond")
client = AsyncOpenAI(api_key=settings.generate_model)


async def node(state: dict) -> dict:
    """
    Generate the AI assistant's response from structured context.
    If stream_callback is provided, streams tokens for real-time TTS.
    """
    t0 = time.perf_counter()
    conv_state = state["state"]
    execution_result = state.get("execution_result", {})
    policy_verdict = state.get("policy_verdict", {})
    stream_callback: Optional[Callable] = state.get("stream_callback")

    # ── If there's a pre-canned message from policy/execution, use it ─────────
    pre_canned = (
        state.get("planned_action", {}).get("message")
        or execution_result.get("message", "")
    )

    # ── Build structured context for the prompt ───────────────────────────────
    customer = conv_state.get("customer", {})
    workflow = conv_state.get("workflow", {})
    tool_result = execution_result.get("result", {})
    tool_data = tool_result.get("data", {}) if isinstance(tool_result, dict) else {}

    rag_answer = ""
    rag_sources = ""
    if execution_result.get("kind") == "rag":
        chunks = execution_result["result"].get("chunks", [])
        rag_answer = " ".join(c["text"] for c in chunks[:2])[:500]
        rag_sources = ", ".join(
            c["source"].replace(".txt", "").replace("_", " ").title()
            for c in chunks[:3]
        )

    ticket_id = tool_data.get("ticket_id") or conv_state.get("ticket_id", "")
    engineer_booking = ""
    if tool_data.get("engineer_booked"):
        engineer_booking = (
            f"Appointment: {tool_data.get('appointment_display', 'tomorrow')}, "
            f"Technician: {tool_data.get('technician_name', 'assigned technician')}, "
            f"Ref: {tool_data.get('booking_ref', '')}"
        )

    refund_ref = ""
    if tool_data.get("refund_triggered"):
        refund_ref = (
            f"Ref: {tool_data.get('refund_ref', '')}, "
            f"Amount: {tool_data.get('formatted_amount', '')}, "
            f"Processing: {tool_data.get('processing_days', 3)} business days"
        )

    policy_block = ""
    if policy_verdict.get("blocked"):
        policy_block = policy_verdict.get("reason", "Policy restriction applied.")

    # Tool error summary
    tool_result_summary = ""
    if isinstance(tool_result, dict):
        if tool_result.get("ok"):
            tool_result_summary = str(tool_data)[:300]
        elif tool_result.get("error"):
            tool_result_summary = f"Error: {tool_result['error']}"

    # Use pre-canned message if available (escalation/policy message)
    if pre_canned:
        response_text = pre_canned
    else:
        prompt = RESPOND_PROMPT.format(
            intent=conv_state.get("intent", {}).get("name", "unknown"),
            workflow_name=workflow.get("name", "N/A"),
            step=workflow.get("step", "N/A"),
            customer_name=customer.get("name", "there"),
            tier=customer.get("tier", "standard"),
            sentiment=conv_state.get("sentiment", "neutral"),
            action_kind=execution_result.get("kind", "unknown"),
            tool_result=tool_result_summary,
            rag_answer=rag_answer,
            rag_sources=rag_sources,
            policy_block=policy_block,
            ticket_id=ticket_id or "None",
            engineer_booking=engineer_booking or "None",
            refund_ref=refund_ref or "None",
        )

        try:
            client_instance = AsyncOpenAI(api_key=settings.openai_api_key)
            response_text = ""

            if stream_callback:
                stream = await client_instance.chat.completions.create(
                    model=settings.generate_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=150,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    response_text += delta
                    if delta.strip():
                        await stream_callback(delta)
            else:
                response = await client_instance.chat.completions.create(
                    model=settings.generate_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=150,
                )
                response_text = response.choices[0].message.content or ""
                conv_state["metrics"]["total_tokens_used"] += (
                    response.usage.total_tokens if response.usage else 0
                )

        except Exception as e:
            logger.error(f"respond node LLM call failed: {e}")
            response_text = (
                "I'm sorry, I encountered a technical issue. "
                "Let me connect you with a specialist who can help."
            )

    # ── Save to transcript with RAG citations ─────────────────────────────────
    citations = []
    if execution_result.get("kind") == "rag":
        citations = [
            c.get("source", "")
            for c in execution_result["result"].get("chunks", [])
        ]

    transcript = conv_state.get("transcript", [])
    transcript.append({
        "role": "assistant",
        "text": response_text,
        "rag_citations": citations,
        "ts": __import__("datetime").datetime.utcnow().isoformat(),
    })
    conv_state["transcript"] = transcript

    # Update ticket_id in state if created this turn
    if ticket_id and not conv_state.get("ticket_id"):
        conv_state["ticket_id"] = ticket_id
        conv_state["flags"]["ticket_created"] = True

    state["generated_reply"] = response_text
    state["reply_citations"] = citations
    state["ticket_id"] = ticket_id
    state["state"] = conv_state

    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("respond", latency_ms)
    logger.info(f"respond: '{response_text[:80]}...'")

    return state
