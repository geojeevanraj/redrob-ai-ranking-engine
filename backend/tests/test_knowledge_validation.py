"""Ontology validation tests."""

from __future__ import annotations

import pytest

from app.knowledge.exceptions import (
    CyclicAliasError,
    DuplicateNodeError,
    InvalidReferenceError,
    MissingCategoryError,
)
from app.knowledge.model import Edge, Node, NodeType, RelationshipType
from app.knowledge.validation import validate_graph


def n(id_: str, *, category: str = "language") -> Node:
    return Node(id=id_, name=id_.title(), type=NodeType.PROGRAMMING_LANGUAGE, category=category)


def test_valid_graph_passes() -> None:
    validate_graph(
        [n("python"), n("java")],
        [Edge(source="python", target="java", relationship=RelationshipType.SIMILAR_TO)],
    )


def test_duplicate_nodes_rejected() -> None:
    with pytest.raises(DuplicateNodeError):
        validate_graph([n("python"), n("python")], [])


def test_missing_category_rejected() -> None:
    with pytest.raises(MissingCategoryError):
        validate_graph([n("python", category="")], [])


def test_invalid_reference_rejected() -> None:
    with pytest.raises(InvalidReferenceError):
        validate_graph(
            [n("python")],
            [Edge(source="python", target="ghost", relationship=RelationshipType.USES)],
        )


def test_cyclic_alias_rejected() -> None:
    nodes = [n("a"), n("b")]
    edges = [
        Edge(source="a", target="b", relationship=RelationshipType.ALIAS_OF),
        Edge(source="b", target="a", relationship=RelationshipType.ALIAS_OF),
    ]
    with pytest.raises(CyclicAliasError):
        validate_graph(nodes, edges)
