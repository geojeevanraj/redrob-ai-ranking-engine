"""Configuration loading tests."""

from __future__ import annotations

from ai.config import AISettings


def test_defaults() -> None:
    settings = AISettings()
    assert settings.primary_llm_provider == "gemini"
    assert settings.fallback_llm_provider == "ollama"
    assert settings.llm_max_retries == 1
    assert settings.llm_timeout == 30.0


def test_env_overrides(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PRIMARY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("FALLBACK_LLM_PROVIDER", "mock")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("LLM_TIMEOUT", "12.5")

    settings = AISettings()
    assert settings.primary_llm_provider == "ollama"
    assert settings.fallback_llm_provider == "mock"
    assert settings.gemini_api_key == "secret-key"
    assert settings.gemini_model == "gemini-1.5-pro"
    assert settings.ollama_host == "http://ollama:11434"
    assert settings.llm_max_retries == 3
    assert settings.llm_timeout == 12.5
