import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.database.session import async_session_factory, engine, Base
from app.database.redis import get_redis_client, close_redis
from app.api.v1.routes import conversations, customers, analytics, crm, billing, scheduling, auth
from app.api.websocket.broadcast import manager
from app.api.websocket.events import TranscriptFinalEvent, TranscriptPartialEvent
from app.gateway.audio import AudioRouter
from app.gateway.session import session_manager
from app.observability.bus import event_bus
from app.speech.tts import EdgeTTSClient
from app.orchestrator.agent import AgentOrchestrator
import app.models
from app.models.conversation import Message
from app.api.v1.routes.analytics import expire_idle_sessions

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

_audio_routers: dict[str, AudioRouter] = {}
_agent = AgentOrchestrator()
_ttl_task: asyncio.Task | None = None

async def _ttl_loop():
    logger.info("Session TTL enforcement loop started")
    while True:
        try:
            await asyncio.sleep(60) # Run every minute
            async with async_session_factory() as db:
                res = await expire_idle_sessions(db=db)
                if res["expired"] > 0:
                    logger.info("TTL Enforcer expired %d idle sessions: %s", res["expired"], res["sessions"])
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in TTL loop: %s", exc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables exist in PostgreSQL
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created")

    await get_redis_client()

    # Initialize the production RAG engine (ChromaDB + FAISS + Redis caching).
    # Loads all 19 KB files from app/orchestrator/rag/data/knowledge_base/ — motor, health, home.
    # Idempotent: skips ChromaDB upsert if already indexed from a prior run.
    try:
        from app.orchestrator.rag import rag_engine
        rag_status = await rag_engine.initialize()
        logger.info(
            "RAG engine ready: %d chunks loaded, %d upserted | "
            "ChromaDB=%s FAISS=%s Redis=%s",
            rag_status.get("documents_loaded", 0),
            rag_status.get("chromadb_upserted", 0),
            rag_status.get("chromadb", "?"),
            rag_status.get("faiss", "?"),
            rag_status.get("redis", "?"),
        )
    except Exception as exc:
        logger.warning("RAG engine initialization failed (non-fatal): %s", exc)

    global _ttl_task
    _ttl_task = asyncio.create_task(_ttl_loop())

    logger.info("Command Center backend started")
    yield
    if _ttl_task:
        _ttl_task.cancel()
    await close_redis()
    logger.info("Command Center backend stopped")



app = FastAPI(
    title="Command Center 3.0",
    version="1.0.0",
    description="AI-first voice contact center — backend API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(crm.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(scheduling.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")


async def _save_message(session_id: str, role: str, content: str, turn_index: int):
    try:
        async with async_session_factory() as db:
            conversation = await session_manager.get_session(db, session_id)
            if conversation:
                message = Message(
                    conversation_id=conversation.conversation_id,
                    role=role,
                    content=content,
                    turn_index=turn_index,
                )
                db.add(message)
                await db.commit()
    except Exception as exc:
        logger.error("Failed to save message for session %s: %s", session_id, exc)


async def _save_message_with_id(session_id: str, role: str, content: str, turn_index: int) -> Message | None:
    try:
        async with async_session_factory() as db:
            conversation = await session_manager.get_session(db, session_id)
            if conversation:
                message = Message(
                    conversation_id=conversation.conversation_id,
                    role=role,
                    content=content,
                    turn_index=turn_index,
                )
                db.add(message)
                await db.commit()
                await db.refresh(message)
                return message
    except Exception as exc:
        logger.error("Failed to save message with id for session %s: %s", session_id, exc)
    return None


async def _run_response_pipeline(
    session_id: str,
    transcript: str,
    turn_index: int,
    websocket: WebSocket,
    audio_router: AudioRouter,
    conversation_id=None,
    message_id=None,
):
    try:
        response_text = await _agent.run_turn(
            session_id=session_id,
            transcript=transcript,
            turn_index=turn_index,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    except Exception as exc:
        logger.error("Orchestrator error session=%s: %s", session_id, exc)
        return

    asyncio.create_task(_save_message(session_id, "agent", response_text, turn_index))

    audio_router.set_tts_active(True)
    try:
        tts = EdgeTTSClient()
        async for audio_chunk in tts.synthesize_streaming(response_text):
            if audio_router.barge_in_detected:
                logger.info("Barge-in during TTS streaming session=%s — stopping", session_id)
                break
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info("WebSocket disconnected during TTS streaming session=%s", session_id)
                break
            await websocket.send_bytes(audio_chunk)
        logger.debug("TTS streaming complete session=%s", session_id)
    except (WebSocketDisconnect, RuntimeError) as exc:
        logger.info("Client disconnected during TTS playback for session %s: %s", session_id, exc)
    except Exception as exc:
        logger.error("TTS error session=%s: %s", session_id, exc)
    finally:
        audio_router.set_tts_active(False)


@app.websocket("/sessions/{session_id}/audio")
async def audio_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info("Audio WebSocket connected: session=%s", session_id)

    audio_router = AudioRouter(session_id=session_id)
    turn_counter: dict = {"n": 0, "conv_id": None}

    try:
        async with async_session_factory() as db:
            conv = await session_manager.get_session(db, session_id)
            if conv:
                turn_counter["conv_id"] = conv.conversation_id
    except Exception as exc:
        logger.warning("Could not fetch conversation_id for session %s: %s", session_id, exc)

    async def on_transcript(event):
        if event.is_final:
            idx = turn_counter["n"]
            turn_counter["n"] += 1

            await event_bus.emit(
                session_id,
                TranscriptFinalEvent(session_id=session_id, text=event.text, turn_index=idx),
            )

            msg = await _save_message_with_id(session_id, "customer", event.text, idx)

            asyncio.create_task(
                _run_response_pipeline(
                    session_id, event.text, idx, websocket, audio_router,
                    conversation_id=turn_counter.get("conv_id"),
                    message_id=msg.message_id if msg else None,
                )
            )
        else:
            await event_bus.emit(
                session_id,
                TranscriptPartialEvent(session_id=session_id, text=event.text),
            )

    async def on_barge_in():
        logger.info("Barge-in — stopping TTS for session %s", session_id)

    audio_router.on_transcript(on_transcript)
    audio_router.on_barge_in(on_barge_in)
    _audio_routers[session_id] = audio_router

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            
            if "bytes" in msg and msg["bytes"]:
                await audio_router.receive_chunk(msg["bytes"])
            elif "text" in msg and msg["text"]:
                import json
                try:
                    data = json.loads(msg["text"])
                    text = data.get("text")
                    if text:
                        logger.info("Received text chat message: %s", text)
                        class FakeEvent:
                            def __init__(self, t):
                                self.is_final = True
                                self.text = t
                        await on_transcript(FakeEvent(text))
                    elif data.get("type") == "flush":
                        logger.info("PTT flush received for session %s — forcing STT finalization", session_id)
                        # Ensure audio_router has a flush method if needed, or ignore
                except Exception as e:
                    logger.error("Error parsing text message: %s", e)

    except WebSocketDisconnect:
        logger.info("Audio WebSocket disconnected: session=%s", session_id)
    except Exception as exc:
        logger.error("Audio WebSocket error session=%s: %s", session_id, exc)
    finally:
        await audio_router.close()
        _audio_routers.pop(session_id, None)
        conv_id = turn_counter.get("conv_id")
        if conv_id:
            asyncio.create_task(_agent.end_session(session_id, conv_id, duration_sec=0))


@app.websocket("/sessions/{session_id}/events")
async def events_websocket(websocket: WebSocket, session_id: str):
    await manager.connect_session(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_session(session_id, websocket)


@app.websocket("/events/stream")
async def supervisor_events_websocket(websocket: WebSocket):
    await manager.connect_supervisor(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_supervisor(websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "command-center-backend", "version": "1.0.0"}
