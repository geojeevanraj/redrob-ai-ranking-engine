"""Mock provider.

A deterministic, offline provider used for tests and local development when no
real backend is configured. It performs no network I/O. Behavior can be tuned
to simulate failures so fallback/retry logic can be exercised.
"""

from __future__ import annotations

from ai.config import AISettings
from ai.providers.base import (
    GenerationParams,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai.providers.exceptions import ProviderError
from ai.providers.registry import register_provider


class MockProvider(LLMProvider):
    """An in-memory provider returning canned responses."""

    def __init__(
        self,
        *,
        model: str = "mock-model",
        response_text: str = '{"ok": true}',
        fail_with: type[ProviderError] | None = None,
        available: bool = True,
    ) -> None:
        self._model = model
        self._response_text = response_text
        self._fail_with = fail_with
        self._available = available
        self.calls = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, messages: list[LLMMessage], params: GenerationParams) -> LLMResponse:
        self.calls += 1
        if self._fail_with is not None:
            raise self._fail_with("Mock provider configured to fail", provider=self.name)
        prompt_chars = sum(len(m.content) for m in messages)
        return LLMResponse(
            text=self._response_text,
            provider=self.name,
            model=self._model,
            usage=TokenUsage(
                input_tokens=prompt_chars // 4,
                output_tokens=len(self._response_text) // 4,
            ),
            response_time_ms=0.0,
            finish_reason="stop",
            raw={"mock": True},
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            model=self._model,
            available=self._available,
            detail="mock" if self._available else "mock unavailable",
        )


@register_provider("mock")
def _build_mock(settings: AISettings) -> MockProvider:
    return MockProvider()
