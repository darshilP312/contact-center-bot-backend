from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.services.llm.client import LLMClient

logger = get_logger("orchestrator.conv_understanding")
_llm = LLMClient()


async def conversation_understanding_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Conversation Understanding Node — maps to diagram node E.

    Responsibilities:
    1. Detect intent from the active domain's intent taxonomy
    2. Extract entities required by the detected intent
    3. Classify sentiment (frustrated/neutral/satisfied/urgent)
    4. Emit intent.detected WebSocket event
    5. Increment turn_count

    Input:  state.raw_transcript, state.domain
    Output: updated state.intent, state.conversation (sentiment, turn_count)
    """
    session_id = state.get("session_id", "none")
    transcript = state.get("raw_transcript", "")
    domain = state.get("domain", "insurance")
    ws = state.get("_ws_connection")
    domain_loader = state.get("_domain_loader")

    # Emit thinking event
    if ws:
        await ws.send_json("agent.thinking", {"node": "conversation_understanding", "status": "running"})

    # Get intent taxonomy for this domain
    intent_taxonomy = []
    if domain_loader:
        intent_taxonomy = domain_loader.get_intent_taxonomy(domain)

    taxonomy_str = json.dumps(
        [{"name": i["name"], "description": i["description"], "required_entities": i.get("required_entities", [])}
         for i in intent_taxonomy],
        indent=2,
    )

    # Get conversation history for context
    history = state.get("transcript_history", [])
    history_str = "\n".join(
        f"{e.role.upper()}: {e.text}" for e in history[-5:]
    ) if history else "(First turn)"

    system_prompt = f"""You are an AI agent processing a customer service conversation in the {domain} domain.

Your task is to analyze the customer's message and return structured JSON with:
1. The most likely intent from the taxonomy
2. Extracted entities
3. Customer sentiment

Intent Taxonomy:
{taxonomy_str}

Recent Conversation History:
{history_str}"""

    user_prompt = f"""Customer said: "{transcript}"

Return JSON with this exact structure:
{{
  "intent_name": "string (must be one of the intent names from the taxonomy, or 'general_query' if uncertain)",
  "confidence": 0.0-1.0,
  "entities": {{"entity_name": "value"}},
  "secondary_intents": ["intent_name"],
  "sentiment": "frustrated|neutral|satisfied|urgent",
  "sentiment_reason": "brief explanation"
}}"""

    try:
        result = await _llm.structured_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            json_schema={},
            session_id=session_id,
            node="conversation_understanding",
        )
    except Exception as e:
        logger.error(
            "Intent classification failed",
            session_id=session_id,
            node="conversation_understanding",
            error=str(e),
        )
        result = {
            "intent_name": "general_query",
            "confidence": 0.5,
            "entities": {},
            "secondary_intents": [],
            "sentiment": "neutral",
        }

    # Update intent model
    intent = state.get("intent")
    if intent:
        intent.name = result.get("intent_name", "general_query")
        intent.confidence = float(result.get("confidence", 0.5))
        intent.entities = result.get("entities", {})
        intent.secondary_intents = result.get("secondary_intents", [])

    # Update conversation state
    conversation = state.get("conversation")
    if conversation:
        conversation.turn_count += 1
        sentiment = result.get("sentiment", "neutral")
        if sentiment in ("frustrated", "neutral", "satisfied", "urgent"):
            conversation.sentiment = sentiment

    logger.info(
        "Intent detected",
        session_id=session_id,
        node="conversation_understanding",
        intent=result.get("intent_name"),
        confidence=result.get("confidence"),
        sentiment=result.get("sentiment"),
    )

    # Emit WebSocket event
    if ws and intent:
        await ws.send_json(
            "intent.detected",
            {
                "name": intent.name,
                "confidence": intent.confidence,
                "entities": intent.entities,
                "sentiment": conversation.sentiment if conversation else "neutral",
                "session_id": session_id,
            },
        )

    return state
