"""Gemini provider (primary).

Wraps the Google Generative Language REST API using httpx (so it is easy to
mock in tests and carries no heavyweight SDK dependency). All transport/API
failures are translated into the `ai.providers.exceptions` hierarchy so the LLM
manager can fall back uniformly.
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
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ai.providers.registry import register_provider


class GeminiProvider(LLMProvider):
    """LLM provider backed by the Gemini generateContent endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        thinking_budget: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._default_temperature = temperature
        self._default_max_tokens = max_tokens
        self._timeout = timeout
        self._thinking_budget = thinking_budget

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    # ── Request construction ────────────────────────────────────
    def _build_payload(
        self, messages: list[LLMMessage], params: GenerationParams
    ) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        system_parts: list[dict[str, str]] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append({"text": msg.content})
                continue
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": params.temperature,
                "maxOutputTokens": params.max_tokens or self._default_max_tokens,
            },
        }
        if self._thinking_budget is not None and self._thinking_budget >= 0:
            payload["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": self._thinking_budget
            }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        return payload

    @staticmethod
    def _parse_response(data: dict[str, Any], provider: str) -> tuple[str, str | None, TokenUsage]:
        candidates = data.get("candidates")
        if not candidates:
            raise InvalidResponseError("Gemini returned no candidates", provider=provider)
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        finish_reason = candidates[0].get("finishReason")
        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            input_tokens=int(usage_meta.get("promptTokenCount", 0)),
            output_tokens=int(usage_meta.get("candidatesTokenCount", 0)),
        )
        return text, finish_reason, usage

    # ── LLMProvider interface ───────────────────────────────────
    async def generate(self, messages: list[LLMMessage], params: GenerationParams) -> LLMResponse:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        timeout = params.timeout or self._timeout
        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    url,
                    params={"key": self._api_key},
                    json=self._build_payload(messages, params),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Gemini timed out: {exc}", provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Gemini network error: {exc}", provider=self.name
            ) from exc

        self._raise_for_status(resp)

        try:
            data = resp.json()
        except ValueError as exc:
            raise InvalidResponseError("Gemini returned non-JSON body", provider=self.name) from exc

        text, finish_reason, usage = self._parse_response(data, self.name)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self._model,
            usage=usage,
            response_time_ms=elapsed_ms,
            finish_reason=finish_reason,
            raw=data,
        )

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code == 200:
            return
        if resp.status_code == 429:
            raise ProviderRateLimitError("Gemini rate limit/quota exceeded", provider=self.name)
        if resp.status_code in (401, 403):
            raise ProviderUnavailableError(
                f"Gemini auth error ({resp.status_code})", provider=self.name
            )
        if resp.status_code >= 500:
            raise ProviderUnavailableError(
                f"Gemini server error ({resp.status_code})", provider=self.name
            )
        raise InvalidResponseError(
            f"Gemini unexpected status {resp.status_code}", provider=self.name
        )

    async def health_check(self) -> ProviderHealth:
        if not self._api_key:
            return ProviderHealth(self.name, self._model, available=False, detail="missing api key")
        url = f"{self._base_url}/models/{self._model}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params={"key": self._api_key})
            available = resp.status_code == 200
            return ProviderHealth(
                self.name, self._model, available=available, detail=f"status={resp.status_code}"
            )
        except httpx.HTTPError as exc:
            return ProviderHealth(self.name, self._model, available=False, detail=str(exc))


@register_provider("gemini")
def _build_gemini(settings: AISettings) -> GeminiProvider:
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        temperature=settings.gemini_temperature,
        max_tokens=settings.gemini_max_tokens,
        timeout=settings.gemini_timeout,
        thinking_budget=settings.gemini_thinking_budget,
    )
