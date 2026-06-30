"""Knowledge repository: storage + query abstraction.

`KnowledgeRepository` defines the contract (create/update/delete + traversal,
lookup, neighbors, relationship queries, alias resolution, search). The default
`InMemoryKnowledgeRepository` keeps the ontology in memory — sufficient for a
mostly-static graph and trivially swappable for a DB/graph-store backend later.

This layer only *stores and queries* relationships. It performs NO inference.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable

from app.knowledge.exceptions import DuplicateNodeError
from app.knowledge.model import Edge, GraphStats, Neighbor, Node, NodeType, RelationshipType

Direction = str  # "out" | "in" | "both"


class KnowledgeRepository(ABC):
    """Contract for knowledge-graph storage and queries."""

    # ── Mutations ───────────────────────────────────────────
    @abstractmethod
    def add_node(self, node: Node) -> Node: ...

    @abstractmethod
    def update_node(self, node: Node) -> Node: ...

    @abstractmethod
    def delete_node(self, node_id: str) -> bool: ...

    @abstractmethod
    def add_edge(self, edge: Edge) -> Edge: ...

    @abstractmethod
    def delete_edge(self, source: str, target: str, relationship: RelationshipType) -> bool: ...

    # ── Lookups ─────────────────────────────────────────────
    @abstractmethod
    def get_node(self, node_id: str) -> Node | None: ...

    @abstractmethod
    def list_nodes(
        self, *, node_type: NodeType | None = None, category: str | None = None
    ) -> list[Node]: ...

    @abstractmethod
    def list_edges(self, *, relationship: RelationshipType | None = None) -> list[Edge]: ...

    # ── Graph queries ───────────────────────────────────────
    @abstractmethod
    def neighbors(
        self,
        node_id: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "both",
    ) -> list[Neighbor]: ...

    @abstractmethod
    def relationships(self, node_id: str) -> list[Edge]: ...

    @abstractmethod
    def resolve_alias(self, name: str) -> Node | None: ...

    @abstractmethod
    def search(self, query: str, *, limit: int = 25) -> list[Node]: ...

    @abstractmethod
    def traverse(
        self,
        start: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "out",
        max_depth: int = 2,
    ) -> list[Node]: ...

    @abstractmethod
    def stats(self) -> GraphStats: ...


class InMemoryKnowledgeRepository(KnowledgeRepository):
    """In-memory adjacency-indexed implementation."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}
        self._alias_index: dict[str, str] = {}  # lowercased term -> node id

    # ── Mutations ───────────────────────────────────────────
    def add_node(self, node: Node) -> Node:
        if node.id in self._nodes:
            raise DuplicateNodeError(f"Duplicate node id: '{node.id}'")
        self._nodes[node.id] = node
        self._index_aliases(node)
        return node

    def update_node(self, node: Node) -> Node:
        self._nodes[node.id] = node
        self._rebuild_alias_index()
        return node

    def delete_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._edges = [e for e in self._edges if e.source != node_id and e.target != node_id]
        self._rebuild_adjacency()
        self._rebuild_alias_index()
        return True

    def add_edge(self, edge: Edge) -> Edge:
        self._edges.append(edge)
        self._out.setdefault(edge.source, []).append(edge)
        self._in.setdefault(edge.target, []).append(edge)
        return edge

    def delete_edge(self, source: str, target: str, relationship: RelationshipType) -> bool:
        key = (source, target, relationship)
        before = len(self._edges)
        self._edges = [e for e in self._edges if e.key() != key]
        if len(self._edges) == before:
            return False
        self._rebuild_adjacency()
        return True

    # ── Lookups ─────────────────────────────────────────────
    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def list_nodes(
        self, *, node_type: NodeType | None = None, category: str | None = None
    ) -> list[Node]:
        nodes: list[Node] = list(self._nodes.values())
        if node_type is not None:
            nodes = [n for n in nodes if n.type == node_type]
        if category is not None:
            nodes = [n for n in nodes if n.category == category]
        return list(nodes)

    def list_edges(self, *, relationship: RelationshipType | None = None) -> list[Edge]:
        if relationship is None:
            return list(self._edges)
        return [e for e in self._edges if e.relationship == relationship]

    # ── Graph queries ───────────────────────────────────────
    def neighbors(
        self,
        node_id: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "both",
    ) -> list[Neighbor]:
        result: list[Neighbor] = []
        for edge, neighbor_id in self._iter_edges(node_id, direction):
            if relationship is not None and edge.relationship != relationship:
                continue
            neighbor = self._nodes.get(neighbor_id)
            if neighbor is not None:
                result.append(Neighbor(edge=edge, node=neighbor))
        return result

    def relationships(self, node_id: str) -> list[Edge]:
        return [e for e in self._edges if e.source == node_id or e.target == node_id]

    def resolve_alias(self, name: str) -> Node | None:
        key = name.strip().lower()
        node_id = self._alias_index.get(key)
        if node_id is None and name in self._nodes:
            node_id = name
        if node_id is None:
            return None
        return self._follow_alias_chain(node_id)

    def search(self, query: str, *, limit: int = 25) -> list[Node]:
        q = query.strip().lower()
        if not q:
            return []
        results: list[Node] = []
        for node in self._nodes.values():
            terms = [node.name, *node.aliases, *node.synonyms]
            if any(q in t.lower() for t in terms):
                results.append(node)
            if len(results) >= limit:
                break
        return results

    def traverse(
        self,
        start: str,
        *,
        relationship: RelationshipType | None = None,
        direction: Direction = "out",
        max_depth: int = 2,
    ) -> list[Node]:
        if start not in self._nodes:
            return []
        visited: set[str] = {start}
        order: list[str] = []
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge, neighbor_id in self._iter_edges(current, direction):
                if relationship is not None and edge.relationship != relationship:
                    continue
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    order.append(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
        return [self._nodes[n] for n in order if n in self._nodes]

    def stats(self) -> GraphStats:
        node_types: dict[str, int] = {}
        for node in self._nodes.values():
            node_types[node.type.value] = node_types.get(node.type.value, 0) + 1
        rel_types: dict[str, int] = {}
        for edge in self._edges:
            rel_types[edge.relationship.value] = rel_types.get(edge.relationship.value, 0) + 1
        return GraphStats(
            node_count=len(self._nodes),
            edge_count=len(self._edges),
            node_types=node_types,
            relationship_types=rel_types,
        )

    # ── Internals ───────────────────────────────────────────
    def _iter_edges(self, node_id: str, direction: Direction) -> Iterable[tuple[Edge, str]]:
        if direction in ("out", "both"):
            for edge in self._out.get(node_id, []):
                yield edge, edge.target
        if direction in ("in", "both"):
            for edge in self._in.get(node_id, []):
                yield edge, edge.source

    def _follow_alias_chain(self, node_id: str) -> Node | None:
        seen: set[str] = set()
        current = node_id
        while current not in seen:
            seen.add(current)
            alias_edges = [
                e for e in self._out.get(current, []) if e.relationship == RelationshipType.ALIAS_OF
            ]
            if not alias_edges:
                break
            current = alias_edges[0].target
        return self._nodes.get(current)

    def _index_aliases(self, node: Node) -> None:
        for term in (node.name, *node.aliases, *node.synonyms):
            self._alias_index.setdefault(term.strip().lower(), node.id)

    def _rebuild_alias_index(self) -> None:
        self._alias_index.clear()
        for node in self._nodes.values():
            self._index_aliases(node)

    def _rebuild_adjacency(self) -> None:
        self._out.clear()
        self._in.clear()
        for edge in self._edges:
            self._out.setdefault(edge.source, []).append(edge)
            self._in.setdefault(edge.target, []).append(edge)
