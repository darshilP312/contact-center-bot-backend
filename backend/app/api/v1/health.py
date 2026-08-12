from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class ReadinessCheck(BaseModel):
    name: str
    status: str
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    checks: list[ReadinessCheck]
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health() -> HealthResponse:
    """
    Liveness check — returns 200 if the server process is running.
    Does not check downstream dependencies.
    """
    return HealthResponse(status="ok", timestamp=datetime.utcnow())


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness check")
async def ready(request: Request) -> ReadinessResponse:
    """
    Readiness check — returns 200 only if all critical dependencies are available:
    - Redis connection
    - At least one domain plugin loaded
    - STT model loaded
    - TTS model loaded
    """
    checks: list[ReadinessCheck] = []
    overall_ok = True

    # Redis
    try:
        redis = request.app.state.redis
        await redis.ping()
        checks.append(ReadinessCheck(name="redis", status="ok"))
    except Exception as e:
        checks.append(ReadinessCheck(name="redis", status="error", detail=str(e)))
        overall_ok = False

    # Domain plugins
    try:
        domain_loader = request.app.state.domain_loader
        loaded = list(domain_loader.domains.keys())
        if loaded:
            checks.append(
                ReadinessCheck(
                    name="domains",
                    status="ok",
                    detail=f"Loaded: {', '.join(loaded)}",
                )
            )
        else:
            checks.append(
                ReadinessCheck(name="domains", status="error", detail="No domains loaded")
            )
            overall_ok = False
    except Exception as e:
        checks.append(ReadinessCheck(name="domains", status="error", detail=str(e)))
        overall_ok = False

    # STT
    try:
        stt = request.app.state.stt
        if stt.is_loaded:
            checks.append(ReadinessCheck(name="stt", status="ok"))
        else:
            checks.append(ReadinessCheck(name="stt", status="error", detail="Model not loaded"))
            overall_ok = False
    except Exception as e:
        checks.append(ReadinessCheck(name="stt", status="error", detail=str(e)))
        overall_ok = False

    # TTS
    try:
        tts = request.app.state.tts
        if tts.is_loaded:
            checks.append(ReadinessCheck(name="tts", status="ok"))
        else:
            checks.append(ReadinessCheck(name="tts", status="error", detail="Model not loaded"))
            overall_ok = False
    except Exception as e:
        checks.append(ReadinessCheck(name="tts", status="error", detail=str(e)))
        overall_ok = False

    return ReadinessResponse(
        status="ready" if overall_ok else "not_ready",
        checks=checks,
        timestamp=datetime.utcnow(),
    )
