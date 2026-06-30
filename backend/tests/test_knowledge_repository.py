"""Knowledge repository / graph query tests."""

from __future__ import annotations

from app.knowledge import Edge, KnowledgeGraph, Node, NodeType, RelationshipType


def build() -> KnowledgeGraph:
    nodes = [
        Node(
            id="python",
            name="Python",
            type=NodeType.PROGRAMMING_LANGUAGE,
            category="language",
            aliases=["py"],
        ),
        Node(id="fastapi", name="FastAPI", type=NodeType.FRAMEWORK, category="backend"),
        Node(id="flask", name="Flask", type=NodeType.FRAMEWORK, category="backend"),
        Node(
            id="rag",
            name="Retrieval-Augmented Generation",
            type=NodeType.AI,
            category="ai_concept",
            aliases=["rag"],
        ),
    ]
    edges = [
        Edge(source="fastapi", target="python", relationship=RelationshipType.DEPENDENT_ON),
        Edge(source="flask", target="python", relationship=RelationshipType.DEPENDENT_ON),
        Edge(source="flask", target="fastapi", relationship=RelationshipType.SIMILAR_TO),
    ]
    return KnowledgeGraph.build(nodes, edges)


def test_get_node() -> None:
    g = build()
    assert g.get_node("python").name == "Python"
    assert g.get_node("missing") is None


def test_list_nodes_filter() -> None:
    g = build()
    frameworks = g.list_nodes(node_type=NodeType.FRAMEWORK)
    assert {n.id for n in frameworks} == {"fastapi", "flask"}


def test_neighbors_direction_and_relationship() -> None:
    g = build()
    # Incoming dependents of python.
    incoming = g.neighbors("python", direction="in")
    assert {n.node.id for n in incoming} == {"fastapi", "flask"}
    # Filter by relationship.
    similar = g.neighbors("flask", relationship=RelationshipType.SIMILAR_TO, direction="out")
    assert [n.node.id for n in similar] == ["fastapi"]


def test_relationships() -> None:
    g = build()
    rels = g.relationships("python")
    assert len(rels) == 2  # two DEPENDENT_ON edges point at python


def test_search() -> None:
    g = build()
    assert {n.id for n in g.search("fast")} == {"fastapi"}
    assert g.search("py")  # alias match for python


def test_resolve_alias() -> None:
    g = build()
    assert g.resolve_alias("py").id == "python"
    assert g.resolve_alias("PYTHON").id == "python"
    assert g.resolve_alias("nope") is None


def test_traverse() -> None:
    g = build()
    reached = g.traverse("flask", direction="out", max_depth=2)
    ids = {n.id for n in reached}
    assert "python" in ids  # flask -> python
    assert "fastapi" in ids  # flask -> fastapi


def test_mutations() -> None:
    g = build()
    g.add_node(Node(id="django", name="Django", type=NodeType.FRAMEWORK, category="backend"))
    assert g.get_node("django") is not None
    g.add_edge(Edge(source="django", target="python", relationship=RelationshipType.DEPENDENT_ON))
    assert any(e.source == "django" for e in g.relationships("python"))

    assert g.delete_edge("django", "python", RelationshipType.DEPENDENT_ON) is True
    assert g.delete_node("django") is True
    assert g.get_node("django") is None


def test_stats() -> None:
    g = build()
    stats = g.stats()
    assert stats.node_count == 4
    assert stats.edge_count == 3
    assert stats.node_types[NodeType.FRAMEWORK.value] == 2
