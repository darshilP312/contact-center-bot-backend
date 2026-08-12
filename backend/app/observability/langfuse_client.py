from __future__ import annotations

from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("observability.langfuse")
settings = get_settings()


class LangfuseClient:
    """
    Langfuse observability client wrapper.

    Silently disabled (no-ops) when LANGFUSE_SECRET_KEY is not configured.
    When enabled, traces all LLM generations, tool calls, and node executions
    grouped by session_id as the Langfuse trace ID.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self.is_enabled = settings.langfuse_enabled

        if self.is_enabled:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse client initialised", node="observability.langfuse")
            except ImportError:
                logger.warning(
                    "langfuse package not installed — tracing disabled. "
                    "Install with: pip install langfuse",
                    node="observability.langfuse",
                )
                self.is_enabled = False
            except Exception as e:
                logger.warning(
                    "Langfuse initialisation failed — tracing disabled",
                    node="observability.langfuse",
                    error=str(e),
                )
                self.is_enabled = False

    async def create_trace(
        self,
        trace_id: str,
        name: str,
        metadata: dict | None = None,
    ) -> Any:
        """Create a new Langfuse trace (maps to a conversation session)."""
        if not self.is_enabled or not self._client:
            return None
        try:
            return self._client.trace(id=trace_id, name=name, metadata=metadata or {})
        except Exception as e:
            logger.warning("Langfuse create_trace failed", error=str(e))
            return None

    async def create_generation(
        self,
        trace_id: str,
        name: str,
        model: str,
        input: Any,
        output: Any,
        usage: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log an LLM generation (prompt + completion) to Langfuse."""
        if not self.is_enabled or not self._client:
            return
        try:
            trace = self._client.trace(id=trace_id)
            trace.generation(
                name=name,
                model=model,
                input=input,
                output=output,
                usage=usage or {},
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning("Langfuse create_generation failed", error=str(e))

    async def create_span(
        self,
        trace_id: str,
        name: str,
        input: Any = None,
        output: Any = None,
        metadata: dict | None = None,
    ) -> None:
        """Log a span (tool call, RAG retrieval, etc.) to Langfuse."""
        if not self.is_enabled or not self._client:
            return
        try:
            trace = self._client.trace(id=trace_id)
            trace.span(
                name=name,
                input=input,
                output=output,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning("Langfuse create_span failed", error=str(e))

    async def flush(self) -> None:
        """Flush all pending Langfuse events before shutdown."""
        if not self.is_enabled or not self._client:
            return
        try:
            self._client.flush()
            logger.info("Langfuse events flushed", node="observability.langfuse")
        except Exception as e:
            logger.warning("Langfuse flush failed", error=str(e))
