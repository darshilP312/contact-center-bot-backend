"""
telemetry.py — Structured per-turn observability.
Logs to Langfuse (if configured) and local console.
Every turn emits: intent, workflow, tool calls, stage latencies, tokens, cost.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("cc.telemetry")

# Optional Langfuse client — gracefully degraded if not configured
_langfuse = None

try:
    from langfuse import Langfuse
    from app.config import settings

    if settings.langfuse_secret_key and settings.langfuse_public_key:
        _langfuse = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse observability initialised.")
    else:
        logger.warning("Langfuse keys not set — observability disabled.")
except ImportError:
    logger.warning("Langfuse not installed — observability disabled.")


# ─── Stage-level timing ────────────────────────────────────────────────────────

_stage_timings: dict[str, float] = {}


def log_stage(stage: str, latency_ms: float, tokens: int = 0) -> None:
    """Record a per-stage latency measurement."""
    _stage_timings[stage] = latency_ms
    logger.debug(f"[STAGE] {stage}: {latency_ms:.1f}ms | tokens: {tokens}")


def log_turn_start(session_id: str, transcript: str) -> None:
    """Mark the beginning of a new turn."""
    global _stage_timings
    _stage_timings = {}
    logger.info(f"[TURN START] session={session_id} | text='{transcript[:80]}'")


def log_turn_complete(
    session_id: str,
    turn_count: int,
    intent: Optional[str],
    workflow: Optional[str],
    step: Optional[str],
    tool_calls: list[str],
    policy_blocked: bool,
    total_tokens: int,
    cost_usd: float,
) -> dict:
    """
    Emit complete turn observability.
    Returns a dict suitable for sending to the frontend as a 'observability' event.
    """
    total_latency = sum(_stage_timings.values())

    log_entry = {
        "session_id": session_id,
        "turn": turn_count,
        "intent": intent,
        "workflow": workflow,
        "step": step,
        "tool_calls": tool_calls,
        "policy_blocked": policy_blocked,
        "stage_latencies_ms": dict(_stage_timings),
        "total_latency_ms": total_latency,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }

    logger.info(
        f"[TURN COMPLETE] session={session_id} turn={turn_count} "
        f"intent={intent} latency={total_latency:.0f}ms tokens={total_tokens}"
    )

    # Budget warning
    if total_latency > 1200:
        logger.warning(
            f"[LATENCY BUDGET EXCEEDED] session={session_id} "
            f"total={total_latency:.0f}ms (budget: 1200ms)"
        )

    # Send to Langfuse
    if _langfuse:
        try:
            trace = _langfuse.trace(
                name="orchestrator_turn",
                session_id=session_id,
                metadata=log_entry,
            )
            for stage, latency in _stage_timings.items():
                _langfuse.span(
                    trace_id=trace.id,
                    name=f"stage_{stage}",
                    metadata={"latency_ms": latency},
                )
        except Exception as e:
            logger.warning(f"Langfuse logging failed: {e}")

    return log_entry
