"""
understand.py — Node 1: UNDERSTAND
Extract intent, secondary intents, entities, and sentiment from the transcript.
Uses a small, fast LLM with JSON-mode output. Pure classification — no prose.
LLM call #1 per turn.
"""

from __future__ import annotations

import json
import logging
import time

from openai import AsyncOpenAI

from app.config import settings
from app.orchestrator.prompts import UNDERSTAND_PROMPT
from app.telemetry import log_stage

logger = logging.getLogger("cc.node.understand")
client = AsyncOpenAI(api_key=settings.openai_api_key)

CONFIDENCE_THRESHOLD = 0.65


async def node(state: dict) -> dict:
    """
    Extract intent, entities, and sentiment from the user transcript.
    Updates state.intent and state.sentiment.
    """
    t0 = time.perf_counter()
    transcript = state.get("transcript_text", "")
    conv_state = state["state"]

    if not transcript:
        logger.warning("understand node called with empty transcript")
        return state

    prompt = UNDERSTAND_PROMPT.format(transcript=transcript)

    try:
        response = await client.chat.completions.create(
            model=settings.understand_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        raw = response.choices[0].message.content
        extracted = json.loads(raw)
        tokens = response.usage.total_tokens if response.usage else 0
    except Exception as e:
        logger.error(f"understand node LLM call failed: {e}")
        extracted = {
            "primary_intent": "unknown",
            "secondary_intents": [],
            "confidence": 0.0,
            "sentiment": "neutral",
            "entities": {},
        }
        tokens = 0

    # Write to state
    conv_state["intent"]["name"] = extracted.get("primary_intent", "unknown")
    conv_state["intent"]["confidence"] = float(extracted.get("confidence", 0.0))
    conv_state["intent"]["entities"] = extracted.get("entities", {})
    conv_state["intent"]["secondary_intents"] = extracted.get("secondary_intents", [])
    conv_state["sentiment"] = extracted.get("sentiment", "neutral")

    # Update metrics
    conv_state["metrics"]["total_tokens_used"] += tokens

    latency_ms = (time.perf_counter() - t0) * 1000
    log_stage("understand", latency_ms, tokens=tokens)

    logger.info(
        f"understand: intent={conv_state['intent']['name']} "
        f"conf={conv_state['intent']['confidence']:.2f} "
        f"sentiment={conv_state['sentiment']}"
    )

    state["state"] = conv_state
    state["understand_result"] = extracted
    return state
