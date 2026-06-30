"""JSON ontology importer."""

from __future__ import annotations

import json
from pathlib import Path

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.importers.base import GraphImporter, parse_graph_dict
from app.knowledge.model import Edge, Node


class JsonImporter(GraphImporter):
    """Loads a `{nodes, edges}` JSON document."""

    def load(self, source: str | Path) -> tuple[list[Node], list[Edge]]:
        try:
            text = Path(source).read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            raise ImportFormatError(f"Could not read JSON ontology: {exc}") from exc
        return parse_graph_dict(data)
