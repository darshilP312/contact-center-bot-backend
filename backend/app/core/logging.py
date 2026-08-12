from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings


def _add_session_id(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Ensure session_id is always present in log events."""
    if "session_id" not in event_dict:
        event_dict["session_id"] = "none"
    return event_dict


def _add_trace_id(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Ensure trace_id is always present in log events."""
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = "none"
    return event_dict


def _add_node(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Ensure node name is always present in log events."""
    if "node" not in event_dict:
        event_dict["node"] = "system"
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for structured JSON logging (production) or
    colored console output (development).

    Every log event will contain: session_id, trace_id, node, level, timestamp.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_session_id,
        _add_trace_id,
        _add_node,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_FORMAT == "json":
        # Production: machine-readable JSON
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.BoundLogger:
    """
    Get a bound structlog logger.

    Args:
        name: Logger name (typically the module name or service name).

    Returns:
        Configured bound logger instance.
    """
    return structlog.get_logger(name)
