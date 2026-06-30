"""LLM manager fallback, retry, timeout, and usage/validation tests."""

from __future__ import annotations

import pytest

from ai.llm.manager import LLMManager, LLMManagerError
from ai.llm.usage import InMemoryUsageTracker
from ai.providers.exceptions import (
    InvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ai.tests.helpers import ScriptedProvider


async def test_primary_success_no_fallback() -> None:
    primary = ScriptedProvider("primary", text="hello")
    fallback = ScriptedProvider("fallback", text="from-fallback")
    manager = LLMManager(primary, fallback, max_retries=0)

    resp = await manager.generate("hi")

    assert resp.text == "hello"
    assert resp.provider == "primary"
    assert primary.calls == 1
    assert fallback.calls == 0


async def test_fallback_on_rate_limit() -> None:
    primary = ScriptedProvider("primary", fail_with=ProviderRateLimitError)
    fallback = ScriptedProvider("fallback", text="from-fallback")
    manager = LLMManager(primary, fallback, max_retries=0)

    resp = await manager.generate("hi")

    assert resp.provider == "fallback"
    assert resp.text == "from-fallback"
    assert fallback.calls == 1


async def test_retry_then_fallback() -> None:
    primary = ScriptedProvider("primary", fail_with=ProviderRateLimitError)
    fallback = ScriptedProvider("fallback", text="ok")
    manager = LLMManager(primary, fallback, max_retries=2)

    resp = await manager.generate("hi")

    # primary attempted max_retries + 1 times before falling back
    assert primary.calls == 3
    assert resp.provider == "fallback"


async def test_all_providers_fail_raises() -> None:
    primary = ScriptedProvider("primary", fail_with=ProviderRateLimitError)
    fallback = ScriptedProvider("fallback", fail_with=InvalidResponseError)
    manager = LLMManager(primary, fallback, max_retries=0)

    with pytest.raises(LLMManagerError):
        await manager.generate("hi")


async def test_timeout_triggers_fallback() -> None:
    primary = ScriptedProvider("primary", delay=0.5)  # slower than timeout
    fallback = ScriptedProvider("fallback", text="fast")
    manager = LLMManager(primary, fallback, max_retries=0, timeout=0.05)

    resp = await manager.generate("hi")

    assert resp.provider == "fallback"


async def test_generate_json_falls_back_on_malformed_primary() -> None:
    primary = ScriptedProvider("primary", text="not json at all")
    fallback = ScriptedProvider("fallback", text='{"valid": true}')
    manager = LLMManager(primary, fallback, max_retries=0)

    resp = await manager.generate_json("hi", required_keys=["valid"])

    assert resp.provider == "fallback"
    assert resp.json_data == {"valid": True}


async def test_usage_recorded_for_success_and_failure() -> None:
    tracker = InMemoryUsageTracker()
    primary = ScriptedProvider("primary", fail_with=ProviderTimeoutError)
    fallback = ScriptedProvider("fallback", text="ok")
    manager = LLMManager(primary, fallback, max_retries=0, usage_tracker=tracker)

    await manager.generate("hi")

    records = tracker.all()
    assert len(records) == 2  # one failed primary, one successful fallback
    assert records[0].success is False
    assert records[0].fallback_used is False
    assert records[1].success is True
    assert records[1].fallback_used is True


async def test_health_reports_both_providers() -> None:
    primary = ScriptedProvider("primary", available=True)
    fallback = ScriptedProvider("fallback", available=False)
    manager = LLMManager(primary, fallback)

    health = await manager.health()

    assert health.primary_provider == "primary"
    assert health.fallback_provider == "fallback"
    assert health.providers["primary"].available is True
    assert health.providers["fallback"].available is False
