"""Smoke tests for the Sprint 0 foundation endpoints.

Verifies the app boots and the three required endpoints respond correctly:
GET /health, GET /version, GET /.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["docs_url"] == "/docs"
    assert body["health_url"] == "/health"


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["environment"] == "testing"


@pytest.mark.asyncio
async def test_version(client: AsyncClient) -> None:
    resp = await client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_version"] == "v1"
    assert "version" in body


@pytest.mark.asyncio
async def test_versioned_health(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert "X-Request-ID" in resp.headers
