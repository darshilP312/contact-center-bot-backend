from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, sessions, websocket, domains

api_router = APIRouter()

# Health & readiness
api_router.include_router(health.router, tags=["Health"])

# Session management
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])

# Domain info
api_router.include_router(domains.router, prefix="/domains", tags=["Domains"])

# WebSocket gateway
api_router.include_router(websocket.router, tags=["WebSocket"])
