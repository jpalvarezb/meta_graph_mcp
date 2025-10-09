"""Structlog logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from .config import get_settings


def configure_logging() -> None:
    """Configure structlog with JSON output."""

    settings = get_settings()
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(message)s",
        force=True,
    )

    if settings.enable_request_logging:
        structlog.get_logger(__name__).info("request_logging_enabled")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger."""

    return structlog.get_logger(name)


__all__ = ["configure_logging", "get_logger"]
