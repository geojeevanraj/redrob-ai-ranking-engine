"""AI service configuration.

Strongly-typed, environment-driven settings for the shared AI infrastructure
(LLM providers, manager, embeddings). Loaded once and cached so every AI engine
reads from a single validated source of truth.

Environment variables (subset):
    PRIMARY_LLM_PROVIDER, FALLBACK_LLM_PROVIDER
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_MAX_TOKENS, GEMINI_TIMEOUT
    OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT
    LLM_TIMEOUT, LLM_MAX_RETRIES
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Configuration for AI providers, the LLM manager, and embeddings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ── Provider selection (Strategy pattern wiring) ────────────
    primary_llm_provider: str = "gemini"
    fallback_llm_provider: str = "ollama"

    # ── Manager-level behavior ──────────────────────────────────
    llm_timeout: float = 30.0
    llm_max_retries: int = 1

    # ── Gemini (primary) ────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0
    gemini_max_tokens: int = 8192
    gemini_timeout: float = 30.0
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # Thinking-token budget for Gemini 2.5+ models. 0 disables "thinking" so
    # structured/JSON responses come back directly and reliably. Set to -1 to
    # leave it unset (for non-thinking models).
    gemini_thinking_budget: int = 0

    # ── Ollama (fallback) ───────────────────────────────────────
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout: float = 60.0

    # ── Embeddings (future sprints) ─────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384


@lru_cache
def get_ai_settings() -> AISettings:
    """Return cached AI settings (single source of truth)."""
    return AISettings()
