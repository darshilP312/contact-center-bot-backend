from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request

from app.core.logging import get_logger
from app.models.audio import AudioPayload

logger = get_logger("api.websocket")
router = APIRouter()


class WebSocketConnection:
    """
    Manages a single WebSocket connection lifecycle.

    Handles:
    - JSON control messages (text frames)
    - Binary PCM audio frames
    - Event emission back to the client
    - STT pipeline integration
    - LangGraph orchestrator invocation
    """

    def __init__(self, websocket: WebSocket, session_id: str, app_state: Any) -> None:
        self.websocket = websocket
        self.session_id = session_id
        self.app_state = app_state
        self.stt = app_state.stt
        self.tts = app_state.tts
        self.redis = app_state.redis
        self.domain_loader = app_state.domain_loader
        self.tool_registry = app_state.tool_registry
        self.rag = app_state.rag
        self.langfuse = app_state.langfuse
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._active = True
        self._domain: str = "insurance"
        self._language: str = "en"
        self._turn_count: int = 0

    async def send_json(self, message_type: str, payload: dict) -> None:
        """Send a JSON event to the client."""
        try:
            await self.websocket.send_text(
                json.dumps({"type": message_type, "payload": payload})
            )
        except Exception as e:
            logger.warning(
                "Failed to send WebSocket message",
                session_id=self.session_id,
                node="websocket",
                error=str(e),
            )

    async def send_binary(self, audio_bytes: bytes) -> None:
        """Send binary TTS audio to the client."""
        try:
            await self.websocket.send_bytes(audio_bytes)
        except Exception as e:
            logger.warning(
                "Failed to send audio bytes",
                session_id=self.session_id,
                node="websocket",
                error=str(e),
            )

    async def handle_session_start(self, payload: dict) -> None:
        """Handle session.start control message."""
        self._domain = payload.get("language", "en") and payload.get("domain", "insurance")
        self._language = payload.get("language", "en")
        self._domain = payload.get("domain", "insurance")

        from app.services.session.manager import SessionManager

        manager = SessionManager(self.redis)
        existing = await manager.get_session(self.session_id)

        if not existing:
            await manager.create_session(
                domain=self._domain,
                language=self._language,
                channel="voice",
                session_id=self.session_id,
            )

        await self.send_json(
            "session.state",
            {
                "session_id": self.session_id,
                "domain": self._domain,
                "language": self._language,
                "status": "active",
            },
        )
        logger.info(
            "Session started via WebSocket",
            session_id=self.session_id,
            node="websocket",
            domain=self._domain,
        )

    async def handle_text_message(self, payload: dict) -> None:
        """Handle text.message — skip STT, go directly to orchestrator."""
        text = payload.get("text", "").strip()
        if not text:
            return

        self._turn_count += 1
        trace_id = str(uuid.uuid4())

        await self.send_json(
            "transcript.final",
            {
                "text": text,
                "session_id": self.session_id,
                "turn_count": self._turn_count,
            },
        )

        await self._run_orchestrator(text, trace_id)

    async def _run_orchestrator(self, transcript: str, trace_id: str) -> None:
        """Invoke the LangGraph orchestrator for a completed transcript."""
        turn_start = time.monotonic()

        await self.send_json("agent.thinking", {"node": "conversation_understanding", "status": "running"})

        try:
            from app.orchestrator.graph import build_graph
            from app.services.session.manager import SessionManager

            manager = SessionManager(self.redis)
            session_state = await manager.get_session(self.session_id)

            graph = build_graph(
                ws_connection=self,
                domain_loader=self.app_state.domain_loader,
                tool_registry=self.app_state.tool_registry,
                rag_node=self.app_state.rag,
                stt=self.app_state.stt,
                tts=self.app_state.tts,
                langfuse=self.app_state.langfuse,
            )

            # Build initial AgentState from session
            from app.orchestrator.state import build_initial_state

            initial_state = await build_initial_state(
                session_id=self.session_id,
                raw_transcript=transcript,
                domain=self._domain,
                language=self._language,
                session_data=session_state,
                redis=self.redis,
            )

            final_state = await graph.ainvoke(initial_state)

            # Persist updated state
            await manager.update_session_from_state(self.session_id, final_state)

            # Send full state snapshot
            await self.send_json(
                "session.state",
                {
                    "session_id": self.session_id,
                    "conversation": final_state["conversation"].model_dump(),
                    "customer": final_state["customer"].model_dump(),
                    "intent": final_state["intent"].model_dump(),
                    "workflow": final_state["workflow"].model_dump(),
                    "flags": final_state["flags"].model_dump(),
                    "metrics": final_state["metrics"].model_dump(),
                },
            )

            # Send metrics update
            turn_ms = int((time.monotonic() - turn_start) * 1000)
            metrics = final_state["metrics"]
            await self.send_json(
                "metrics.update",
                {
                    "session_id": self.session_id,
                    "turn_latencies_ms": metrics.turn_latencies_ms,
                    "total_tokens_used": metrics.total_tokens_used,
                    "total_cost": metrics.total_cost,
                    "tool_calls_made": metrics.tool_calls_made,
                    "glass_to_glass_ms": turn_ms,
                },
            )

            # Clear all thinking nodes after the turn completes
            for node in ("conversation_understanding", "planner", "guardrails",
                         "business_router", "rag", "tool_caller",
                         "workflow_executor", "response_generator", "escalation_handler"):
                await self.send_json("agent.thinking", {"node": node, "status": "done"})

        except Exception as e:
            logger.error(
                "Orchestrator error",
                session_id=self.session_id,
                node="websocket",
                error=str(e),
                exc_info=True,
            )
            await self.send_json(
                "error",
                {
                    "code": "LLM_ERROR",
                    "message": "An error occurred processing your request. Please try again.",
                    "session_id": self.session_id,
                    "recoverable": True,
                },
            )

    async def handle_audio_frame(self, audio_bytes: bytes) -> None:
        """Handle binary PCM audio frame — queue for STT pipeline."""
        try:
            self._audio_queue.put_nowait(audio_bytes)
        except asyncio.QueueFull:
            logger.warning(
                "Audio queue full — dropping frame",
                session_id=self.session_id,
                node="websocket",
            )

    async def _stt_pipeline_loop(self) -> None:
        """Background task: drain audio queue through STT pipeline."""
        from app.services.stt.pipeline import STTPipeline

        pipeline = STTPipeline(
            stt=self.stt,
            language=self._language,
            on_partial=lambda text: asyncio.create_task(
                self.send_json("transcript.partial", {"text": text, "session_id": self.session_id})
            ),
            on_final=lambda text: asyncio.create_task(
                self._on_final_transcript(text)
            ),
        )

        async def audio_generator():
            while self._active:
                try:
                    chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
                    yield chunk
                except asyncio.TimeoutError:
                    continue

        await pipeline.process(audio_generator())

    async def _on_final_transcript(self, text: str) -> None:
        """Called when VAD detects end of speech and STT produces final transcript."""
        self._turn_count += 1
        trace_id = str(uuid.uuid4())

        await self.send_json(
            "transcript.final",
            {
                "text": text,
                "session_id": self.session_id,
                "turn_count": self._turn_count,
            },
        )

        await self._run_orchestrator(text, trace_id)

    async def run(self) -> None:
        """Main connection loop — receive and dispatch messages."""
        # Start STT pipeline as background task
        stt_task = asyncio.create_task(self._stt_pipeline_loop())

        try:
            while True:
                try:
                    message = await self.websocket.receive()
                except WebSocketDisconnect:
                    break

                if message["type"] == "websocket.disconnect":
                    break
                elif message["type"] == "websocket.receive":
                    if "bytes" in message and message["bytes"]:
                        await self.handle_audio_frame(message["bytes"])
                    elif "text" in message and message["text"]:
                        try:
                            data = json.loads(message["text"])
                            msg_type = data.get("type")
                            payload = data.get("payload", {})

                            if msg_type == "session.start":
                                await self.handle_session_start(payload)
                            elif msg_type == "text.message":
                                await self.handle_text_message(payload)
                            elif msg_type == "session.end":
                                break
                        except json.JSONDecodeError:
                            await self.send_json(
                                "error",
                                {
                                    "code": "WEBSOCKET_ERROR",
                                    "message": "Invalid JSON message",
                                    "recoverable": True,
                                },
                            )
        finally:
            self._active = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass
            logger.info(
                "WebSocket connection closed",
                session_id=self.session_id,
                node="websocket",
            )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket gateway for a conversation session.

    Accepts:
    - Binary frames: raw PCM 16kHz 16-bit mono audio
    - Text frames: JSON control messages (session.start, text.message, session.end)

    Emits:
    - transcript.partial, transcript.final, agent.thinking, intent.detected,
      workflow.update, response.text, session.state, session.escalated,
      metrics.update, error
    - Binary: TTS audio chunks
    """
    await websocket.accept()

    logger.info(
        "WebSocket connection accepted",
        session_id=session_id,
        node="websocket",
    )

    connection = WebSocketConnection(
        websocket=websocket,
        session_id=session_id,
        app_state=websocket.app.state,  # type: ignore[attr-defined]
    )

    await connection.run()
