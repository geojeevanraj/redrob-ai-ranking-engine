"""KnowledgeGraph facade.

The consumer-facing object used by API endpoints and every future AI engine.
Wraps a `KnowledgeRepository`, validates ontology data on build, and exposes
query + mutation operations. It performs NO inference — it only stores and
returns relationships that were explicitly loaded.
"""

from __future__ import annotations

from app.knowledge.model import Edge, GraphStats, Neighbor, Node, NodeType, RelationshipType
from app.knowledge.repository import Direction, InMemoryKnowledgeRepository, KnowledgeRepository
from app.knowledge.validation import validate_graph


class KnowledgeGraph:
    """Facade over a knowledge repository."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repo = repository

    @classmethod
    def build(
        cls,
        nodes: list[Node],
        edges: list[Edge],
        *,
        validate: bool = True,
        repository: KnowledgeRepository | None = None,
    ) -> KnowledgeGraph:
        """Validate and load nodes/edges into a repository."""
        if validate:
            validate_graph(nodes, edges)
        repo = repository or InMemoryKnowledgeRepository()
        for node in nodes:
            repo.add_node(node)
        for edge in edges:
            repo.add_edge(edge)
        return cls(repo)

    # ── Lookups / queries (delegated) ───────────────────────
    def get_node(self, node_id: str) -> Node | None:
        return self._repo.get_node(node_id)

    def list_nodes(
        self, *, node_type: NodeType | None = None, category: str | None = None
    ) -> list[Node]:
        return self._repo.list_nodes(node_type=node_type, category=category)

    def list_edges(self, *, relationship: RelationshipType | None = None) -> list[Edge]:
        return self._repo.list_edges(relationship=relationship)

    def neighbors(
        self,
        node_id: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "both",
    ) -> list[Neighbor]:
        return self._repo.neighbors(node_id, relationship=relationship, direction=direction)

    def relationships(self, node_id: str) -> list[Edge]:
        return self._repo.relationships(node_id)

    def resolve_alias(self, name: str) -> Node | None:
        return self._repo.resolve_alias(name)

    def search(self, query: str, *, limit: int = 25) -> list[Node]:
        return self._repo.search(query, limit=limit)

    def traverse(
        self,
        start: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "out",
        max_depth: int = 2,
    ) -> list[Node]:
        return self._repo.traverse(
            start, relationship=relationship, direction=direction, max_depth=max_depth
        )

    def stats(self) -> GraphStats:
        return self._repo.stats()

    # ── Mutations (delegated) ───────────────────────────────
    def add_node(self, node: Node) -> Node:
        return self._repo.add_node(node)

    def update_node(self, node: Node) -> Node:
        return self._repo.update_node(node)

    def delete_node(self, node_id: str) -> bool:
        return self._repo.delete_node(node_id)

    def add_edge(self, edge: Edge) -> Edge:
        return self._repo.add_edge(edge)

    def delete_edge(self, source: str, target: str, relationship: RelationshipType) -> bool:
        return self._repo.delete_edge(source, target, relationship)
