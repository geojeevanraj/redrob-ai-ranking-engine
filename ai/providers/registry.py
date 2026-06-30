"""Provider registry — the extensibility seam.

New providers register a builder via the `@register_provider("name")` decorator.
The LLM manager builds providers by name through `build_provider`, so adding a
new backend (OpenAI, Claude, OpenRouter, DeepSeek, ...) never requires touching
consumer or business logic — only adding a new provider module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ai.providers.exceptions import UnknownProviderError

if TYPE_CHECKING:
    from ai.config import AISettings
    from ai.providers.base import LLMProvider

# name -> builder(settings) -> provider
ProviderBuilder = Callable[["AISettings"], "LLMProvider"]
_BUILDERS: dict[str, ProviderBuilder] = {}


def register_provider(name: str) -> Callable[[ProviderBuilder], ProviderBuilder]:
    """Class/function decorator that registers a provider builder by name."""

    def decorator(builder: ProviderBuilder) -> ProviderBuilder:
        _BUILDERS[name.lower()] = builder
        return builder

    return decorator


def build_provider(name: str, settings: AISettings) -> LLMProvider:
    """Instantiate a registered provider by name."""
    key = name.lower()
    builder = _BUILDERS.get(key)
    if builder is None:
        raise UnknownProviderError(
            f"Unknown LLM provider '{name}'. Registered: {sorted(_BUILDERS)}",
            provider=name,
        )
    return builder(settings)


def available_providers() -> list[str]:
    """Return the sorted list of registered provider names."""
    return sorted(_BUILDERS)
