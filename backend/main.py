from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.api.router import api_router

settings = get_settings()


def create_app() -> FastAPI:
    """
    FastAPI application factory.

    Creates the FastAPI app with:
    - Lifespan events (startup/shutdown)
    - CORS middleware
    - API router at /api/v1
    - Optional frontend static file serving
    - OpenAPI 3.1 schema at /api/v1/docs
    """
    app = FastAPI(
        title="Enterprise Voice-First AI Command Center",
        description=(
            "A production-grade, domain-agnostic enterprise AI platform for "
            "real-time multi-modal (Voice + Text) contact center conversations."
        ),
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API Routes ────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── Frontend Static Files (optional) ─────────────────────────────────────
    if settings.FRONTEND_ENABLED:
        frontend_dist = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "frontend", "dist"
        )
        if os.path.isdir(frontend_dist):
            app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
