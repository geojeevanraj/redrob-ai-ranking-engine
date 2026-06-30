"""Knowledge Graph API tests (uses the real seed graph; no DB)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_nodes(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/nodes", params={"type": "framework", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) <= 5
    assert all(n["type"] == "framework" for n in body)


async def test_get_node(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/node/python")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Python"


async def test_get_node_by_alias(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/node/k8s")
    assert resp.status_code == 200
    assert resp.json()["id"] == "kubernetes"


async def test_get_node_missing_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/node/does-not-exist")
    assert resp.status_code == 404


async def test_search(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/search", params={"q": "lang"})
    assert resp.status_code == 200
    ids = {n["id"] for n in resp.json()}
    assert "langchain" in ids


async def test_relationships_for_node(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/relationships", params={"node_id": "fastapi"})
    assert resp.status_code == 200
    assert any(e["target"] == "python" for e in resp.json())


async def test_neighbors(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/node/rag/neighbors", params={"relationship": "USES"})
    assert resp.status_code == 200
    assert any(n["node"]["id"] == "embeddings" for n in resp.json())


async def test_stats(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/knowledge/stats")
    assert resp.status_code == 200
    assert resp.json()["node_count"] >= 150
