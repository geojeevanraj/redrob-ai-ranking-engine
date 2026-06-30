"""Importer interface + shared dict-to-model parsing.

Importers are the data-driven entry point: the graph is never hardcoded in
Python. Each importer turns a source (file/dir) into `(nodes, edges)`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.model import Edge, Node


class GraphImporter(ABC):
    """Contract for ontology importers."""

    @abstractmethod
    def load(self, source: str | Path) -> tuple[list[Node], list[Edge]]:
        """Parse a source into nodes and edges."""


def parse_graph_dict(data: dict[str, Any]) -> tuple[list[Node], list[Edge]]:
    """Convert a `{"nodes": [...], "edges": [...]}` dict into models."""
    if not isinstance(data, dict):
        raise ImportFormatError("Ontology document must be a mapping with nodes/edges")
    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ImportFormatError("'nodes' and 'edges' must be lists")
    nodes = [Node.model_validate(n) for n in raw_nodes]
    edges = [Edge.model_validate(e) for e in raw_edges]
    return nodes, edges
