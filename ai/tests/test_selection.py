"""Provider selection / registry tests."""

from __future__ import annotations

import pytest

from ai.config import AISettings
from ai.llm.manager import LLMManager
from ai.providers import available_providers, build_provider
from ai.providers.exceptions import UnknownProviderError
from ai.providers.gemini import GeminiProvider
from ai.providers.ollama import OllamaProvider


def test_builtin_providers_registered() -> None:
    names = available_providers()
    assert {"gemini", "ollama", "mock"}.issubset(set(names))


def test_build_provider_by_name() -> None:
    settings = AISettings()
    assert isinstance(build_provider("gemini", settings), GeminiProvider)
    assert isinstance(build_provider("ollama", settings), OllamaProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(UnknownProviderError):
        build_provider("does-not-exist", AISettings())


def test_manager_from_settings_selects_primary_and_fallback() -> None:
    settings = AISettings(primary_llm_provider="gemini", fallback_llm_provider="ollama")
    manager = LLMManager.from_settings(settings)
    assert manager.primary.name == "gemini"
    assert manager.fallback is not None
    assert manager.fallback.name == "ollama"


def test_manager_no_fallback_when_same_as_primary() -> None:
    settings = AISettings(primary_llm_provider="mock", fallback_llm_provider="mock")
    manager = LLMManager.from_settings(settings)
    assert manager.primary.name == "mock"
    assert manager.fallback is None
