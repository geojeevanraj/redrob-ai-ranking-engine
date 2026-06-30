"""Seed ontology tests — verifies the bundled dataset loads and is usable."""

from __future__ import annotations

from app.knowledge import RelationshipType, load_seed_graph

graph = load_seed_graph()


def test_seed_has_enough_nodes() -> None:
    stats = graph.stats()
    assert stats.node_count >= 150
    assert stats.edge_count > 0


def test_seed_contains_key_technologies() -> None:
    for node_id in [
        "python",
        "fastapi",
        "react",
        "kubernetes",
        "rag",
        "langchain",
        "faiss",
        "postgresql",
        "mcp",
        "crewai",
    ]:
        assert graph.get_node(node_id) is not None, node_id


def test_seed_alias_resolution() -> None:
    assert graph.resolve_alias("k8s").id == "kubernetes"
    assert graph.resolve_alias("postgres").id == "postgresql"
    assert graph.resolve_alias("js").id == "javascript"


def test_seed_relationships_stored() -> None:
    # FastAPI depends on Python (explicitly stored, not inferred).
    deps = graph.neighbors("fastapi", relationship=RelationshipType.DEPENDENT_ON, direction="out")
    assert any(n.node.id == "python" for n in deps)
    # RAG uses embeddings.
    uses = graph.neighbors("rag", relationship=RelationshipType.USES, direction="out")
    assert any(n.node.id == "embeddings" for n in uses)


def test_seed_search() -> None:
    results = graph.search("kuber")
    assert any(n.id == "kubernetes" for n in results)
