"""Structured logging helpers for the AI infrastructure.

Self-contained so the `ai` package does not depend on the backend app. Emits a
single structured log line per LLM request with the fields required by the
spec: request id, provider, model, execution time, success/failure, whether a
fallback was used, and token usage when available.
"""

from __future__ import annotations

import logging
from typing import Any

_CONFIGURED = False


def _ensure_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger = logging.getLogger("ai")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _CONFIGURED = True


def get_ai_logger(name: str = "ai") -> logging.Logger:
    """Return a configured logger under the `ai` namespace."""
    _ensure_configured()
    return logging.getLogger(name)


def log_llm_request(
    logger: logging.Logger,
    *,
    request_id: str,
    provider: str,
    model: str,
    execution_ms: float,
    success: bool,
    fallback_used: bool,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> None:
    """Emit one structured log line describing an LLM request outcome."""
    fields: dict[str, Any] = {
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "execution_ms": round(execution_ms, 1),
        "success": success,
        "fallback_used": fallback_used,
    }
    if input_tokens is not None:
        fields["input_tokens"] = input_tokens
    if output_tokens is not None:
        fields["output_tokens"] = output_tokens
    if error:
        fields["error"] = error

    rendered = " ".join(f"{k}={v}" for k, v in fields.items())
    if success:
        logger.info("llm_request %s", rendered)
    else:
        logger.warning("llm_request %s", rendered)
