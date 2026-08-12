from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.logging import get_logger

logger = get_logger("observability.tracer")

_tracer_provider: TracerProvider | None = None


def setup_tracer(service_name: str = "voice-ai-command-center") -> None:
    """
    Configure OpenTelemetry tracing.

    Uses ConsoleSpanExporter for development. In production, replace with
    Azure Monitor or OTLP exporter.

    Args:
        service_name: Service name for trace identification.
    """
    global _tracer_provider

    provider = TracerProvider()

    # Development: export traces to console
    # Production: use OTLP exporter or Azure Monitor
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    logger.info("OpenTelemetry tracer configured", node="observability.tracer", service=service_name)


def get_tracer(name: str = "app") -> trace.Tracer:
    """Get a named tracer instance."""
    return trace.get_tracer(name)
