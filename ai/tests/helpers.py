"""Shared test helpers for AI infrastructure tests.

Provides controllable fake providers and an httpx MockTransport factory so all
external API calls are mocked — no real network requests are ever made.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from ai.providers.base import (
    GenerationParams,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai.providers.exceptions import ProviderError


class ScriptedProvider(LLMProvider):
    """A provider whose behavior is fully scripted for tests."""

    def __init__(
        self,
        name: str = "scripted",
        *,
        text: str = '{"ok": true}',
        fail_with: type[ProviderError] | None = None,
        delay: float = 0.0,
        available: bool = True,
    ) -> None:
        self._name = name
        self._text = text
        self._fail_with = fail_with
        self._delay = delay
        self._available = available
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return f"{self._name}-model"

    async def generate(self, messages: list[LLMMessage], params: GenerationParams) -> LLMResponse:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail_with is not None:
            raise self._fail_with("scripted failure", provider=self._name)
        return LLMResponse(
            text=self._text,
            provider=self._name,
            model=self.model,
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            response_time_ms=1.0,
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(self._name, self.model, available=self._available)


def mock_client_factory(handler: Callable[[httpx.Request], httpx.Response]):
    """Return a replacement for httpx.AsyncClient that uses a MockTransport.

    Usage:
        monkeypatch.setattr(gemini.httpx, "AsyncClient",
                            mock_client_factory(handler))
    """
    real_client = httpx.AsyncClient  # capture before any monkeypatching

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)  # type: ignore[arg-type]

    return factory
