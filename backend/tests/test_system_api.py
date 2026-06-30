"""System status endpoint test (LLM + DB session faked)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from ai.llm.manager import ManagerHealth
from ai.providers.base import ProviderHealth
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.dependencies.common import get_llm_manager
from app.main import create_app


class FakeManager:
    async def health(self) -> ManagerHealth:
        return ManagerHealth(
            primary_provider="gemini",
            fallback_provider="ollama",
            providers={
                "gemini": ProviderHealth("gemini", "gemini-1.5-flash", available=True, detail="ok"),
                "ollama": ProviderHealth("ollama", "llama3.1", available=False, detail="down"),
            },
        )


class FakeSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_llm_manager] = lambda: FakeManager()

    async def _fake_session() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = _fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_system_status(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/system/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm"]["primary_provider"] == "gemini"
    assert body["llm"]["providers"]["gemini"]["available"] is True
    assert body["llm"]["providers"]["ollama"]["available"] is False
    assert body["knowledge_graph"]["loaded"] is True
    assert body["database_connected"] is True
    assert body["config"]["gemini_model"] == "gemini-2.5-flash"
