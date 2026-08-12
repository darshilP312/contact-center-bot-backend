from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.core.logging import get_logger
from app.models.transcript import TranscriptEntry
from app.services.llm.client import LLMClient

logger = get_logger("orchestrator.response_generator")
_llm = LLMClient()


async def response_generator_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Response Generator Node — maps to diagram node Y (Response Generation).

    Responsibilities:
    1. Build a rich, contextual prompt from full AgentState
    2. Stream LLM tokens directly to TTS pipeline
    3. Append response to transcript history
    4. Emit response.text WebSocket event
    5. Update ObservabilityMetrics with token count

    Input:  Full AgentState (all context, tool results, RAG, history)
    Output: state.response_text, state.transcript_history updated
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    tts = state.get("_tts")
    domain = state.get("domain", "insurance")
    intent = state.get("intent")
    customer = state.get("customer")
    workflow = state.get("workflow")
    flags = state.get("flags")
    metrics = state.get("metrics")
    transcript_history = list(state.get("transcript_history") or [])
    tool_results = state.get("tool_results") or []
    rag_result = state.get("rag_result") or ""
    rag_citations = state.get("rag_citations") or []
    policy_violations = state.get("policy_violations") or []
    clarification_needed = state.get("clarification_needed", False)
    clarification_question = state.get("clarification_question")
    language = state.get("active_language", "en")
    transcript = state.get("pii_masked_transcript", state.get("raw_transcript", ""))

    if ws:
        await ws.send_json("agent.thinking", {"node": "response_generator", "status": "running"})

    # Format tool results for prompt
    tool_results_str = ""
    for tr in tool_results[-5:]:  # Last 5 tool results
        if tr.get("status") == "success":
            tool_results_str += f"- {tr['tool']}: {json.dumps(tr['result'])[:300]}\n"

    # Format conversation history
    history_str = ""
    for entry in transcript_history[-5:]:
        role_label = {"customer": "Customer", "agent": "Agent", "system": "System"}.get(entry.role, "Unknown")
        history_str += f"{role_label}: {entry.text}\n"

    # Build the response prompt
    prompt = f"""You are an empathetic, professional AI assistant for an enterprise {domain} contact center.

CONTEXT:
Domain: {domain}
Intent: {intent.name if intent else "unknown"} (confidence: {intent.confidence if intent else 0:.0%})
Customer: {customer.name or "Unknown"}, Tier: {customer.tier or "standard"}, Verified: {customer.verified if customer else False}
Workflow: {workflow.name if workflow else "None"}, Current Step: {workflow.step if workflow else "None"}
Active Language: {language}

TOOL RESULTS:
{tool_results_str or "No tool calls were made."}

KNOWLEDGE RETRIEVED (from knowledge base):
{rag_result or "No knowledge base content retrieved."}
{f"Sources: {', '.join(rag_citations)}" if rag_citations else ""}

RECENT CONVERSATION:
{history_str or "(No previous conversation)"}

POLICY NOTES:
{chr(10).join(f"- {v}" for v in policy_violations) if policy_violations else "No policy violations."}

CUSTOMER MESSAGE: "{transcript}"

{"TASK: Ask the customer: " + clarification_question if clarification_needed and clarification_question else "TASK: Generate a complete, helpful response to the customer's request based on the tool results and knowledge above."}

RESPONSE GUIDELINES:
- Be empathetic, professional, and concise (1-3 sentences).
- Use the customer's name if known (e.g., Priya).
- Reference specific claim IDs, ticket numbers, or policy numbers from tool results.
- STRICT GROUNDING REQUIREMENT: Answer based EXCLUSIVELY on the KNOWLEDGE RETRIEVED section above and official tool results.
- NEVER invent placeholder URLs (like insure.example.com), fake phone numbers (like 1800-XXX-XXXX), or general non-policy answers.
- If RAG context was retrieved, cite the exact coverage rules, exclusions, or terms directly from the policy document.
- If KNOWLEDGE RETRIEVED is empty and no tool results exist for a domain query, inform the customer politely that the detail is not found in their policy documentation.
- Respond in {language} language.
- Do NOT mention internal tool names or system processes to the customer."""

    start_time = time.monotonic()
    full_response = ""
    total_tokens = 0

    try:
        if tts and ws:
            # Stream mode: token → TTS → audio
            from app.services.tts.stream import TTSStreamCoordinator
            coordinator = TTSStreamCoordinator(tts, ws_send_binary=ws.send_binary)

            async def token_gen():
                nonlocal total_tokens
                async for token in _llm.stream_completion(
                    messages=[{"role": "user", "content": prompt}],
                    session_id=session_id,
                    node="response_generator",
                ):
                    total_tokens += 1
                    yield token

            full_response = await coordinator.stream_text(token_gen())
        else:
            # Non-streaming fallback
            full_response = await _llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                session_id=session_id,
                node="response_generator",
            )
            total_tokens = len(full_response.split())  # Approximate

    except Exception as e:
        logger.error(
            "Response generation failed",
            session_id=session_id,
            node="response_generator",
            error=str(e),
        )
        full_response = "I apologize, I encountered an issue generating a response. Please try again."

    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Update state
    state["response_text"] = full_response
    state["response_audio_queued"] = bool(tts)

    # Append to transcript history
    new_entry = TranscriptEntry(
        session_id=session_id,
        role="agent",
        text=full_response,
        rag_citations=rag_citations,
    )
    transcript_history.append(new_entry)
    state["transcript_history"] = transcript_history

    # Update metrics
    if metrics:
        turn_id = str(state.get("conversation", {}).turn_count if hasattr(state.get("conversation", {}), "turn_count") else len(transcript_history))
        metrics.turn_latencies_ms[turn_id] = latency_ms
        metrics.total_tokens_used += total_tokens
        # Approximate cost (Groq/Gemini is free or near-free, use placeholder)
        metrics.total_cost += total_tokens * 0.000001

    # Also save to STM
    try:
        redis = getattr(ws, "redis", None) if ws else None
        if redis:
            from app.orchestrator.memory.short_term import ShortTermMemory
            stm = ShortTermMemory(redis)
            await stm.append_entry(session_id, new_entry)
    except Exception:
        pass  # Non-critical

    # Emit WebSocket event
    if ws:
        await ws.send_json(
            "response.text",
            {
                "text": full_response,
                "is_final": True,
                "rag_used": bool(rag_result),
                "session_id": session_id,
            },
        )

    logger.info(
        "Response generated",
        session_id=session_id,
        node="response_generator",
        latency_ms=latency_ms,
        response_length=len(full_response),
        rag_used=bool(rag_result),
    )

    return state
