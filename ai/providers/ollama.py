"""Ollama provider (fallback).

Wraps a local Ollama server's chat API via httpx. Used automatically by the LLM
manager when the primary provider fails. Translates transport failures into the
shared provider exception hierarchy.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ai.config import AISettings
from ai.providers.base import (
    GenerationParams,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderHealth,
    TokenUsage,
)
from ai.providers.exceptions import (
    InvalidResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ai.providers.registry import register_provider


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama server (`/api/chat`)."""

    def __init__(self, *, host: str, model: str, timeout: float = 60.0) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def _build_payload(
        self, messages: list[LLMMessage], params: GenerationParams
    ) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": params.temperature}
        if params.max_tokens:
            options["num_predict"] = params.max_tokens
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }

    async def generate(self, messages: list[LLMMessage], params: GenerationParams) -> LLMResponse:
        url = f"{self._host}/api/chat"
        timeout = params.timeout or self._timeout
        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=self._build_payload(messages, params))
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Ollama timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Ollama network error: {exc}", provider=self.name
            ) from exc

        if resp.status_code != 200:
            raise ProviderUnavailableError(f"Ollama status {resp.status_code}", provider=self.name)

        try:
            data = resp.json()
        except ValueError as exc:
            raise InvalidResponseError("Ollama returned non-JSON body", provider=self.name) from exc

        text = data.get("message", {}).get("content", "")
        usage = TokenUsage(
            input_tokens=int(data.get("prompt_eval_count", 0)),
            output_tokens=int(data.get("eval_count", 0)),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self._model,
            usage=usage,
            response_time_ms=elapsed_ms,
            finish_reason=data.get("done_reason"),
            raw=data,
        )

    async def health_check(self) -> ProviderHealth:
        url = f"{self._host}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
            available = resp.status_code == 200
            return ProviderHealth(
                self.name, self._model, available=available, detail=f"status={resp.status_code}"
            )
        except httpx.HTTPError as exc:
            return ProviderHealth(self.name, self._model, available=False, detail=str(exc))


@register_provider("ollama")
def _build_ollama(settings: AISettings) -> OllamaProvider:
    return OllamaProvider(
        host=settings.ollama_host,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout,
    )
