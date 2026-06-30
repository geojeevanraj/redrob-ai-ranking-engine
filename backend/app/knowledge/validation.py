"""Ontology validation.

Validates a set of nodes/edges before they are loaded into a repository:
duplicate node ids, missing categories, invalid edge references, and cyclic
ALIAS_OF relationships. Raises a specific `KnowledgeError` subclass on failure.
"""

from __future__ import annotations

from app.knowledge.exceptions import (
    CyclicAliasError,
    DuplicateNodeError,
    InvalidReferenceError,
    MissingCategoryError,
)
from app.knowledge.model import Edge, Node, RelationshipType


def validate_graph(nodes: list[Node], edges: list[Edge]) -> None:
    """Validate nodes/edges, raising on the first structural problem."""
    _check_duplicate_nodes(nodes)
    _check_categories(nodes)
    _check_references(nodes, edges)
    _check_alias_cycles(nodes, edges)


def _check_duplicate_nodes(nodes: list[Node]) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise DuplicateNodeError(f"Duplicate node id: '{node.id}'")
        seen.add(node.id)


def _check_categories(nodes: list[Node]) -> None:
    for node in nodes:
        if not node.category or not node.category.strip():
            raise MissingCategoryError(f"Node '{node.id}' is missing a category")


def _check_references(nodes: list[Node], edges: list[Edge]) -> None:
    ids = {n.id for n in nodes}
    for edge in edges:
        if edge.source not in ids:
            raise InvalidReferenceError(f"Edge references unknown source node '{edge.source}'")
        if edge.target not in ids:
            raise InvalidReferenceError(f"Edge references unknown target node '{edge.target}'")


def _check_alias_cycles(nodes: list[Node], edges: list[Edge]) -> None:
    # Build ALIAS_OF adjacency and detect any cycle via DFS.
    alias_adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relationship == RelationshipType.ALIAS_OF:
            alias_adj.setdefault(edge.source, []).append(edge.target)

    visiting: set[str] = set()
    done: set[str] = set()

    def dfs(node_id: str) -> None:
        if node_id in done:
            return
        if node_id in visiting:
            raise CyclicAliasError(f"Cyclic ALIAS_OF detected at node '{node_id}'")
        visiting.add(node_id)
        for nxt in alias_adj.get(node_id, []):
            dfs(nxt)
        visiting.discard(node_id)
        done.add(node_id)

    for start in list(alias_adj):
        dfs(start)
