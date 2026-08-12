from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger("lifespan")


def _patch_windows_symlink() -> None:
    """
    Patch os.symlink on Windows to fallback to file copying when
    unprivileged symlinks are disabled by Windows Group Policy / AVD.
    """
    import os
    import shutil

    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    if hasattr(os, "symlink"):
        _orig_symlink = os.symlink

        def _safe_symlink(
            src: str | os.PathLike[str],
            dst: str | os.PathLike[str],
            target_is_directory: bool = False,
            *,
            dir_fd: Any = None,
        ) -> None:
            try:
                _orig_symlink(src, dst, target_is_directory=target_is_directory, dir_fd=dir_fd)
            except OSError as e:
                if getattr(e, "winerror", None) == 1314 or "1314" in str(e):
                    try:
                        src_str = str(src)
                        dst_str = str(dst)
                        abs_src = (
                            src_str
                            if os.path.isabs(src_str)
                            else os.path.normpath(os.path.join(os.path.dirname(dst_str), src_str))
                        )
                        if os.path.isdir(abs_src):
                            shutil.copytree(abs_src, dst_str, dirs_exist_ok=True)
                        elif os.path.isfile(abs_src):
                            shutil.copyfile(abs_src, dst_str)
                    except Exception:
                        pass
                else:
                    raise

        os.symlink = _safe_symlink  # type: ignore[assignment]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup:
    - Configures structured logging
    - Initialises Redis connection pool
    - Discovers and loads all domain plugins
    - Warms up STT model (background task)
    - Warms up TTS model (background task)
    - Builds FAISS RAG indices per domain (background task)
    - Registers all tools in the tool registry

    Shutdown:
    - Closes Redis connection pool
    - Flushes Langfuse trace buffer
    """
    settings = get_settings()

    # ── Startup ────────────────────────────────────────────────────────────────
    _patch_windows_symlink()
    configure_logging()
    logger.info("Starting Enterprise Voice-First AI Command Center", node="lifespan")

    # 1. Redis
    from app.services.session.redis_client import get_redis_client

    redis_client = await get_redis_client()
    app.state.redis = redis_client
    logger.info("Redis connection established", node="lifespan")

    # 2. Domain plugin loader
    from app.domains.loader import DomainLoader

    domain_loader = DomainLoader(settings.DOMAINS_DIR)
    await domain_loader.load_all()
    app.state.domain_loader = domain_loader
    logger.info(
        "Domain plugins loaded",
        node="lifespan",
        domains=list(domain_loader.domains.keys()),
    )

    # 3. Tool registry
    from app.tools.registry import ToolRegistry

    tool_registry = ToolRegistry()
    tool_registry.discover_and_register()
    app.state.tool_registry = tool_registry
    logger.info(
        "Tool registry initialised",
        node="lifespan",
        tool_count=tool_registry.count,
    )

    # 4. STT model warm-up (background, non-blocking)
    from app.services.stt.whisper_stt import WhisperSTT

    stt = WhisperSTT(
        model_size=settings.STT_MODEL_SIZE,
        model_dir=settings.STT_MODEL_DIR,
        compute_type=settings.STT_COMPUTE_TYPE,
        device=settings.STT_DEVICE,
    )
    app.state.stt = stt
    asyncio.create_task(stt.warm_up())

    # 5. TTS model warm-up (background, non-blocking)
    if settings.TTS_PROVIDER == "kokoro":
        from app.services.tts.kokoro_tts import KokoroTTS

        tts = KokoroTTS(
            model_dir=settings.TTS_KOKORO_MODEL_DIR,
            default_voice=settings.TTS_DEFAULT_VOICE,
        )
    else:
        from app.services.tts.edge_tts_fallback import EdgeTTSFallback

        tts = EdgeTTSFallback(default_voice=settings.TTS_EDGE_VOICE)

    app.state.tts = tts
    asyncio.create_task(tts.warm_up())

    # 6. FAISS RAG indices per domain (background, non-blocking)
    from app.orchestrator.nodes.rag import RAGNode

    rag_node = RAGNode(domain_loader=domain_loader)
    app.state.rag = rag_node
    asyncio.create_task(rag_node.build_all_indices())

    # 7. Langfuse (optional observability)
    from app.observability.langfuse_client import LangfuseClient

    langfuse_client = LangfuseClient()
    app.state.langfuse = langfuse_client
    if settings.langfuse_enabled:
        logger.info("Langfuse tracing enabled", node="lifespan")
    else:
        logger.info("Langfuse tracing disabled (no keys configured)", node="lifespan")

    logger.info(
        "Application startup complete — ready to serve",
        node="lifespan",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
    )

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Application shutting down", node="lifespan")

    if settings.langfuse_enabled:
        await langfuse_client.flush()
        logger.info("Langfuse traces flushed", node="lifespan")

    await redis_client.aclose()
    logger.info("Redis connection closed", node="lifespan")

    logger.info("Application shutdown complete", node="lifespan")
