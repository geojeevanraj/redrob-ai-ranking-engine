"""LLM Manager — the single entry point for every AI request.

Business logic and AI engines must call `LLMManager.generate(...)` /
`generate_json(...)` and never talk to a provider directly. The manager owns:

    - provider selection (primary + optional fallback)
    - automatic fallback on any provider failure
    - per-provider retry with bounded attempts
    - timeout enforcement
    - centralized error handling
    - response validation (text / JSON)
    - usage tracking
    - structured request logging
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ai.config import AISettings, get_ai_settings
from ai.llm.logging import get_ai_logger, log_llm_request
from ai.llm.usage import InMemoryUsageTracker, UsageRecord, UsageTracker, estimate_cost
from ai.providers import build_provider
from ai.providers.base import GenerationParams, LLMMessage, LLMProvider, LLMResponse, ProviderHealth
from ai.providers.exceptions import ProviderError, ProviderTimeoutError

logger = get_ai_logger("ai.llm.manager")

# A provider call: given a provider, produce a response.
ProviderCall = Callable[[LLMProvider], Awaitable[LLMResponse]]


class LLMManagerError(Exception):
    """Raised when all providers (primary + fallback) have failed."""


@dataclass
class ManagerHealth:
    """Aggregate health snapshot across configured providers."""

    primary_provider: str
    fallback_provider: str | None
    providers: dict[str, ProviderHealth]


class LLMManager:
    """Coordinates providers with fallback, retries, validation, and logging."""

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None = None,
        *,
        max_retries: int = 1,
        timeout: float = 30.0,
        usage_tracker: UsageTracker | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max(0, max_retries)
        self.timeout = timeout
        self.usage_tracker = usage_tracker or InMemoryUsageTracker()

    # ── Construction ────────────────────────────────────────────
    @classmethod
    def from_settings(
        cls,
        settings: AISettings | None = None,
        *,
        usage_tracker: UsageTracker | None = None,
    ) -> LLMManager:
        """Build a manager from configuration using the provider registry."""
        settings = settings or get_ai_settings()
        primary = build_provider(settings.primary_llm_provider, settings)
        fallback: LLMProvider | None = None
        if settings.fallback_llm_provider and (
            settings.fallback_llm_provider.lower() != settings.primary_llm_provider.lower()
        ):
            fallback = build_provider(settings.fallback_llm_provider, settings)
        return cls(
            primary,
            fallback,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            usage_tracker=usage_tracker,
        )

    # ── Public API ──────────────────────────────────────────────
    async def generate(
        self,
        prompt: str | list[LLMMessage],
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Generate text, falling back to the secondary provider on failure."""
        messages = self._to_messages(prompt, system)
        params = GenerationParams(temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        return await self._execute(lambda p: p.generate(messages, params), params)

    async def generate_json(
        self,
        prompt: str | list[LLMMessage],
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float | None = None,
        required_keys: list[str] | None = None,
    ) -> LLMResponse:
        """Generate and validate JSON, falling back on failure.

        Malformed JSON raises `InvalidResponseError` inside the provider call,
        which the manager treats as a fallback-eligible failure.
        """
        messages = self._to_messages(prompt, system)
        params = GenerationParams(temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        return await self._execute(
            lambda p: p.generate_json(messages, params, required_keys=required_keys),
            params,
        )

    async def health(self) -> ManagerHealth:
        """Probe all configured providers and report availability."""
        providers: dict[str, ProviderHealth] = {}
        providers[self.primary.name] = await self.primary.health_check()
        if self.fallback is not None:
            providers[self.fallback.name] = await self.fallback.health_check()
        return ManagerHealth(
            primary_provider=self.primary.name,
            fallback_provider=self.fallback.name if self.fallback else None,
            providers=providers,
        )

    # ── Internals ───────────────────────────────────────────────
    @staticmethod
    def _to_messages(prompt: str | list[LLMMessage], system: str | None) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        if system:
            messages.append(LLMMessage.system(system))
        if isinstance(prompt, str):
            messages.append(LLMMessage.user(prompt))
        else:
            messages.extend(prompt)
        return messages

    async def _execute(self, call: ProviderCall, params: GenerationParams) -> LLMResponse:
        """Run `call` against primary then fallback, with retries and logging."""
        providers = [self.primary] + ([self.fallback] if self.fallback else [])
        effective_timeout = params.timeout or self.timeout
        last_error: Exception | None = None

        for index, provider in enumerate(providers):
            fallback_used = index > 0
            for _attempt in range(self.max_retries + 1):
                request_id = uuid.uuid4().hex[:12]
                started = time.perf_counter()
                try:
                    response = await asyncio.wait_for(call(provider), timeout=effective_timeout)
                except TimeoutError as exc:
                    last_error = ProviderTimeoutError(
                        f"{provider.name} exceeded {effective_timeout}s", provider=provider.name
                    )
                    self._log_failure(request_id, provider, started, fallback_used, str(last_error))
                    _ = exc  # keep cause readable in logs
                    continue
                except ProviderError as exc:
                    last_error = exc
                    self._log_failure(request_id, provider, started, fallback_used, str(exc))
                    continue

                self._record_success(request_id, provider, response, fallback_used)
                return response

        raise LLMManagerError(
            f"All providers failed (primary='{self.primary.name}', "
            f"fallback='{self.fallback.name if self.fallback else None}'): {last_error}"
        ) from last_error

    def _record_success(
        self,
        request_id: str,
        provider: LLMProvider,
        response: LLMResponse,
        fallback_used: bool,
    ) -> None:
        cost = estimate_cost(
            response.model, response.usage.input_tokens, response.usage.output_tokens
        )
        self.usage_tracker.record(
            UsageRecord(
                request_id=request_id,
                provider=provider.name,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                estimated_cost=cost,
                response_time_ms=response.response_time_ms,
                success=True,
                fallback_used=fallback_used,
            )
        )
        log_llm_request(
            logger,
            request_id=request_id,
            provider=provider.name,
            model=response.model,
            execution_ms=response.response_time_ms,
            success=True,
            fallback_used=fallback_used,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def _log_failure(
        self,
        request_id: str,
        provider: LLMProvider,
        started: float,
        fallback_used: bool,
        error: str,
    ) -> None:
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.usage_tracker.record(
            UsageRecord(
                request_id=request_id,
                provider=provider.name,
                model=provider.model,
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                response_time_ms=elapsed_ms,
                success=False,
                fallback_used=fallback_used,
            )
        )
        log_llm_request(
            logger,
            request_id=request_id,
            provider=provider.name,
            model=provider.model,
            execution_ms=elapsed_ms,
            success=False,
            fallback_used=fallback_used,
            error=error,
        )
