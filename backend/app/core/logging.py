"""Application logging configuration.

Provides a single `configure_logging()` entry point that sets up either
human-readable or JSON-structured logs based on settings. Call once at startup.
"""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    """Configure root logging handlers/formatters idempotently."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_json:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    else:
        formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Align uvicorn loggers with our handler/level.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).handlers = [handler]
        logging.getLogger(name).propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (ensures configuration has run)."""
    configure_logging()
    return logging.getLogger(name)
