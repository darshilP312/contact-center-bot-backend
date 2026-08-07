"""
main.py — FastAPI application entry point.
Provides:
  - REST endpoints for tool testing (/tools/...)
  - WebSocket endpoint for voice/text sessions (/ws/{session_id})
  - Health check (/health)
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.state import ConversationState
from app.orchestrator.graph import run_turn
from app.tools.router import router as tools_router
from app.telemetry import log_turn_start

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("cc.main")

from app.storage import init_storage, get_storage, BaseSessionStorage

session_storage: BaseSessionStorage = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_storage
    session_storage = await init_storage()
    yield
    if session_storage:
        await session_storage.close()
    logger.info("Storage shutdown complete.")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Contact Centre",
    description="Enterprise AI orchestration layer for contact centres.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── WebSocket session handler ─────────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    """
    Bidirectional WebSocket for voice/text contact centre sessions.

    Client → Server message types:
      control(start|stop|barge_in), audio_chunk, text_input

    Server → Client message types:
      transcript_partial, transcript_final, assistant_text,
      audio_chunk, state_update, ticket, policy_block,
      handoff_summary, observability, error
    """
    await ws.accept()
    logger.info(f"WebSocket connected: session={session_id}")

    # Load or create session state from storage
    try:
        loaded_state = await get_storage().get_session(session_id)
        state = loaded_state if loaded_state else ConversationState(session_id=session_id)
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        state = ConversationState(session_id=session_id)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            # ── Control: start ────────────────────────────────────────────────
            if msg_type == "control" and msg.get("action") == "start":
                await ws.send_json({
                    "type": "state_update",
                    "workflow_name": state.workflow.name,
                    "workflow_step": state.workflow.step,
                    "completed_steps": state.workflow.completed_steps,
                    "flags": state.flags.model_dump(),
                    "sentiment": state.sentiment,
                    "customer_tier": state.customer.tier,
                })
                logger.info(f"Session started: {session_id}")

            # ── Control: stop ────────────────────────────────────────────────
            elif msg_type == "control" and msg.get("action") == "stop":
                logger.info(f"Session stopped: {session_id}")
                break

            # ── Control: barge-in ────────────────────────────────────────────
            elif msg_type == "control" and msg.get("action") == "barge_in":
                state.flags.barge_in_detected = True
                logger.info(f"Barge-in detected: {session_id}")
                # TTS interruption is handled client-side; backend just flags it

            # ── Text input (dev mode — bypasses STT) ─────────────────────────
            elif msg_type in ("text_input", "transcript_final"):
                transcript = msg.get("text", "").strip()
                if not transcript:
                    continue

                log_turn_start(session_id, transcript)
                state.add_transcript("user", transcript)

                # Echo the final transcript back to client
                await ws.send_json({
                    "type": "transcript_final",
                    "text": transcript,
                    "confidence": 1.0,
                })

                # Streaming token callback for real-time TTS
                token_buffer = []

                async def stream_callback(token: str):
                    token_buffer.append(token)
                    await ws.send_json({
                        "type": "assistant_text",
                        "text": token,
                        "is_streaming": True,
                    })

                # Run the orchestrator turn
                state, result = await run_turn(state, transcript, stream_callback)

                # Send final assembled text
                full_reply = result.get("generated_reply", "")
                await ws.send_json({
                    "type": "assistant_text",
                    "text": full_reply,
                    "is_streaming": False,
                    "rag_citations": [
                        {"source": c, "chunk": "", "score": 0.9}
                        for c in (result.get("reply_citations") or [])
                    ],
                })

                # Push state update
                await ws.send_json({
                    "type": "state_update",
                    "workflow_name": state.workflow.name,
                    "workflow_step": state.workflow.step,
                    "completed_steps": state.workflow.completed_steps,
                    "flags": state.flags.model_dump(),
                    "sentiment": state.sentiment,
                    "customer_tier": state.customer.tier,
                })

                # Push ticket if newly created
                ticket_id = result.get("ticket_id") or state.ticket_id
                if ticket_id and state.flags.ticket_created:
                    tool_data = state.working_memory.last_tool_result or {}
                    await ws.send_json({
                        "type": "ticket",
                        "id": ticket_id,
                        "ticket_type": tool_data.get("data", {}).get("ticket_type", "incident"),
                        "summary": tool_data.get("data", {}).get("summary", ""),
                    })

                # Push policy block notification if blocked
                policy_verdict = result.get("policy_verdict", {})
                if policy_verdict and policy_verdict.get("blocked"):
                    await ws.send_json({
                        "type": "policy_block",
                        "rule": policy_verdict.get("reason", ""),
                        "message": result.get("planned_action", {}).get("message", ""),
                        "required_action": policy_verdict.get(
                            "required_action", {}
                        ).get("kind", ""),
                    })

                # Push handoff summary if escalated
                if state.flags.escalated and state.handoff_summary:
                    await ws.send_json({
                        "type": "handoff_summary",
                        "summary": state.handoff_summary,
                        "ticket_id": state.ticket_id,
                        "sentiment": state.sentiment,
                    })

                # Push observability
                obs = result.get("observability_event", {})
                if obs:
                    await ws.send_json({
                        "type": "observability",
                        "turn": state.turn_count,
                        "stage_latencies_ms": obs.get("stage_latencies_ms", {}),
                        "total_tokens": obs.get("total_tokens", 0),
                        "cost_usd": obs.get("cost_usd", 0.0),
                        "tool_calls": obs.get("tool_calls", []),
                        "intent": obs.get("intent"),
                    })

                # Persist state to storage (1 hour TTL)
                await get_storage().save_session(state, ttl_seconds=3600)

            # ── Audio chunk — forward to STT (Phase 3) ───────────────────────
            elif msg_type == "audio_chunk":
                # Phase 3: Forward to Azure Speech / Deepgram streaming STT
                # For now: log receipt
                seq = msg.get("seq", 0)
                if seq % 50 == 0:  # Log every 50th chunk
                    logger.debug(f"Audio chunk received: seq={seq}, session={session_id}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
        # Persist final state with longer TTL on disconnect
        try:
            await get_storage().save_session(state, ttl_seconds=86400)
        except Exception as e:
            logger.error(f"Failed to persist state on disconnect: {e}")

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await ws.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred. Please try again.",
            })
        except Exception:
            pass
