"""LLM provider package (Strategy pattern).

Importing this package self-registers the built-in providers (Gemini, Ollama,
Mock) with the provider registry so the LLM manager can build them by name.
"""

# Import concrete providers for their registration side effects.
from ai.providers import gemini as _gemini  # noqa: F401
from ai.providers import mock as _mock  # noqa: F401
from ai.providers import ollama as _ollama  # noqa: F401
from ai.providers.base import (
    GenerationParams,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai.providers.registry import available_providers, build_provider, register_provider

__all__ = [
    "GenerationParams",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "ProviderHealth",
    "TokenUsage",
    "available_providers",
    "build_provider",
    "register_provider",
]
