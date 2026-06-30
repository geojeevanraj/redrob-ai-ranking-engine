"""LLM provider abstraction (Strategy pattern).

Every concrete provider (Gemini, Ollama, and future ones like OpenAI, Claude,
OpenRouter, DeepSeek) implements this interface. Consumers never depend on a
concrete provider — they go through the LLM manager, which depends only on
`LLMProvider`.

The interface is intentionally small and generic:
    - generate()       primary text generation
    - generate_json()  text generation + strict JSON parsing/validation
    - health_check()   provider availability probe
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMMessage:
    """A single chat message in a prompt."""

    role: str  # "system" | "user" | "assistant"
    content: str

    @classmethod
    def system(cls, content: str) -> LLMMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> LLMMessage:
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> LLMMessage:
        return cls(role="assistant", content=content)


@dataclass(frozen=True)
class TokenUsage:
    """Token counts reported by (or estimated for) a provider call."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """Normalized response returned by every provider.

    Carries the generated text, the provider/model that produced it, token
    usage, timing, and — when `generate_json` is used — the parsed `json_data`.
    """

    text: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    response_time_ms: float = 0.0
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    json_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationParams:
    """Tunable parameters for a single generation request."""

    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: float | None = None


@dataclass(frozen=True)
class ProviderHealth:
    """Result of a provider health probe."""

    provider: str
    model: str
    available: bool
    detail: str = ""


class LLMProvider(ABC):
    """Contract for large-language-model backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier (e.g. 'gemini', 'ollama')."""

    @property
    @abstractmethod
    def model(self) -> str:
        """The model this provider instance targets."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        params: GenerationParams,
    ) -> LLMResponse:
        """Generate a text completion for the given messages.

        Implementations must translate transport/API failures into the
        `ai.providers.exceptions` hierarchy so the manager can fall back.
        """

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Probe provider availability without performing real generation."""

    async def generate_json(
        self,
        messages: list[LLMMessage],
        params: GenerationParams,
        *,
        required_keys: list[str] | None = None,
    ) -> LLMResponse:
        """Generate, then parse + validate the output as JSON.

        Concrete providers inherit this; it reuses `generate()` and the shared
        validators so JSON handling is identical across providers. Raises
        `InvalidResponseError` on malformed JSON before business logic sees it.
        """
        # Lazy import avoids any package import-time cycle.
        from ai.llm.validation import extract_json, validate_json

        response = await self.generate(messages, params)
        data = extract_json(response.text, provider=self.name)
        validate_json(data, required_keys=required_keys, provider=self.name)
        response.json_data = data
        return response
