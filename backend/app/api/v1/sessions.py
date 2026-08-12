from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger("api.sessions")
router = APIRouter()


class CreateSessionRequest(BaseModel):
    domain: str = "insurance"
    language: str = "en"
    channel: str = "voice"


class CreateSessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    domain: str
    language: str
    channel: str


class SessionStateResponse(BaseModel):
    session_id: str
    conversation: dict
    customer: dict
    intent: dict
    workflow: dict
    flags: dict
    metrics: dict


class EndSessionResponse(BaseModel):
    session_id: str
    ended_at: datetime


class TranscriptResponse(BaseModel):
    session_id: str
    entries: list[dict]


class MetricsResponse(BaseModel):
    session_id: str
    turn_latencies_ms: dict
    total_tokens_used: int
    total_cost: float
    tool_calls_made: int


@router.post("", response_model=CreateSessionResponse, status_code=201, summary="Create session")
async def create_session(
    body: CreateSessionRequest, request: Request
) -> CreateSessionResponse:
    """
    Create a new conversation session.

    Returns a session_id that must be used for:
    - WebSocket connection: ws://host/api/v1/ws/{session_id}
    - Subsequent REST calls to this endpoint
    """
    from app.services.session.manager import SessionManager

    manager = SessionManager(request.app.state.redis)

    # Validate domain is loaded
    domain_loader = request.app.state.domain_loader
    if body.domain not in domain_loader.domains:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{body.domain}' is not loaded. Available: {list(domain_loader.domains.keys())}",
        )

    session = await manager.create_session(
        domain=body.domain,
        language=body.language,
        channel=body.channel,
    )

    logger.info(
        "Session created",
        session_id=session.session_id,
        node="api.sessions",
        domain=body.domain,
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        domain=body.domain,
        language=body.language,
        channel=body.channel,
    )


@router.get("/{session_id}", response_model=SessionStateResponse, summary="Get session state")
async def get_session(session_id: str, request: Request) -> SessionStateResponse:
    """Get the full state of an existing session."""
    from app.services.session.manager import SessionManager

    manager = SessionManager(request.app.state.redis)
    state = await manager.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return SessionStateResponse(
        session_id=session_id,
        conversation=state["conversation"],
        customer=state["customer"],
        intent=state["intent"],
        workflow=state["workflow"],
        flags=state["flags"],
        metrics=state["metrics"],
    )


@router.delete("/{session_id}", response_model=EndSessionResponse, summary="End session")
async def end_session(session_id: str, request: Request) -> EndSessionResponse:
    """End and clean up a session."""
    from app.services.session.manager import SessionManager

    manager = SessionManager(request.app.state.redis)
    ended = await manager.delete_session(session_id)

    if not ended:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    logger.info("Session ended", session_id=session_id, node="api.sessions")

    return EndSessionResponse(session_id=session_id, ended_at=datetime.utcnow())


@router.get("/{session_id}/transcript", response_model=TranscriptResponse, summary="Get transcript")
async def get_transcript(session_id: str, request: Request) -> TranscriptResponse:
    """Get the full conversation transcript for a session."""
    from app.orchestrator.memory.short_term import ShortTermMemory

    stm = ShortTermMemory(request.app.state.redis)
    entries = await stm.get_history(session_id, n=1000)

    return TranscriptResponse(
        session_id=session_id,
        entries=[e.model_dump() for e in entries],
    )


@router.get("/{session_id}/metrics", response_model=MetricsResponse, summary="Get metrics")
async def get_metrics(session_id: str, request: Request) -> MetricsResponse:
    """Get observability metrics for a session."""
    from app.services.session.manager import SessionManager

    manager = SessionManager(request.app.state.redis)
    state = await manager.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    metrics = state.get("metrics", {})
    return MetricsResponse(
        session_id=session_id,
        turn_latencies_ms=metrics.get("turn_latencies_ms", {}),
        total_tokens_used=metrics.get("total_tokens_used", 0),
        total_cost=metrics.get("total_cost", 0.0),
        tool_calls_made=metrics.get("tool_calls_made", 0),
    )
