"""Knowledge Graph query endpoints (read-only).

GET /knowledge/nodes                      list/filter nodes
GET /knowledge/node/{node_id}             fetch a node
GET /knowledge/node/{node_id}/neighbors   neighbors of a node
GET /knowledge/relationships              list edges (optionally for a node)
GET /knowledge/search                     search nodes by name/alias/synonym
GET /knowledge/stats                      graph summary counts
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import NotFoundError
from app.dependencies import get_knowledge_graph
from app.knowledge import (
    Edge,
    GraphStats,
    KnowledgeGraph,
    Neighbor,
    Node,
    NodeType,
    RelationshipType,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

GraphDep = Annotated[KnowledgeGraph, Depends(get_knowledge_graph)]


@router.get("/nodes", response_model=list[Node], summary="List/filter nodes")
def list_nodes(
    graph: GraphDep,
    node_type: NodeType | None = Query(default=None, alias="type"),
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Node]:
    nodes = graph.list_nodes(node_type=node_type, category=category)
    return nodes[offset : offset + limit]


@router.get("/search", response_model=list[Node], summary="Search nodes")
def search_nodes(graph: GraphDep, q: str, limit: int = 25) -> list[Node]:
    return graph.search(q, limit=limit)


@router.get("/relationships", response_model=list[Edge], summary="List relationships")
def list_relationships(
    graph: GraphDep,
    node_id: str | None = None,
    relationship: RelationshipType | None = None,
) -> list[Edge]:
    if node_id is not None:
        edges = graph.relationships(node_id)
        if relationship is not None:
            edges = [e for e in edges if e.relationship == relationship]
        return edges
    return graph.list_edges(relationship=relationship)


@router.get("/stats", response_model=GraphStats, summary="Graph statistics")
def graph_stats(graph: GraphDep) -> GraphStats:
    return graph.stats()


@router.get("/node/{node_id}", response_model=Node, summary="Get a node")
def get_node(node_id: str, graph: GraphDep) -> Node:
    node = graph.get_node(node_id)
    if node is None:
        # Fall back to alias resolution before giving up.
        node = graph.resolve_alias(node_id)
    if node is None:
        raise NotFoundError(f"Node '{node_id}' not found")
    return node


@router.get(
    "/node/{node_id}/neighbors",
    response_model=list[Neighbor],
    summary="Get a node's neighbors",
)
def get_neighbors(
    node_id: str,
    graph: GraphDep,
    relationship: RelationshipType | None = None,
    direction: str = "both",
) -> list[Neighbor]:
    if graph.get_node(node_id) is None:
        raise NotFoundError(f"Node '{node_id}' not found")
    return graph.neighbors(node_id, relationship=relationship, direction=direction)
