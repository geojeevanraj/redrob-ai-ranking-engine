"""Provider HTTP-mapping tests using httpx.MockTransport (no real network)."""

from __future__ import annotations

import httpx
import pytest

from ai.providers import gemini, ollama
from ai.providers.base import GenerationParams, LLMMessage
from ai.providers.exceptions import ProviderRateLimitError, ProviderTimeoutError
from ai.tests.helpers import mock_client_factory

PARAMS = GenerationParams(temperature=0.0, max_tokens=128)
MESSAGES = [LLMMessage.system("be brief"), LLMMessage.user("hello")]


def _gemini_provider() -> gemini.GeminiProvider:
    return gemini.GeminiProvider(
        api_key="test-key",
        model="gemini-1.5-flash",
        base_url="https://example.test/v1beta",
    )


async def test_gemini_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "hi there"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
            },
        )

    monkeypatch.setattr(gemini.httpx, "AsyncClient", mock_client_factory(handler))
    resp = await _gemini_provider().generate(MESSAGES, PARAMS)

    assert resp.text == "hi there"
    assert resp.provider == "gemini"
    assert resp.usage.input_tokens == 7
    assert resp.usage.output_tokens == 3


async def test_gemini_rate_limit_maps_to_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "quota"})

    monkeypatch.setattr(gemini.httpx, "AsyncClient", mock_client_factory(handler))
    with pytest.raises(ProviderRateLimitError):
        await _gemini_provider().generate(MESSAGES, PARAMS)


async def test_gemini_timeout_maps_to_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(gemini.httpx, "AsyncClient", mock_client_factory(handler))
    with pytest.raises(ProviderTimeoutError):
        await _gemini_provider().generate(MESSAGES, PARAMS)


async def test_ollama_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "pong"},
                "prompt_eval_count": 5,
                "eval_count": 2,
                "done_reason": "stop",
            },
        )

    monkeypatch.setattr(ollama.httpx, "AsyncClient", mock_client_factory(handler))
    provider = ollama.OllamaProvider(host="http://localhost:11434", model="llama3.1")
    resp = await provider.generate(MESSAGES, PARAMS)

    assert resp.text == "pong"
    assert resp.provider == "ollama"
    assert resp.usage.output_tokens == 2


async def test_gemini_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "models/gemini-1.5-flash"})

    monkeypatch.setattr(gemini.httpx, "AsyncClient", mock_client_factory(handler))
    health = await _gemini_provider().health_check()
    assert health.available is True
