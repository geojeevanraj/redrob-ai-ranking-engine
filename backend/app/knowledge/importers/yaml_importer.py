"""YAML ontology importer (PyYAML imported lazily)."""

from __future__ import annotations

from pathlib import Path

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.importers.base import GraphImporter, parse_graph_dict
from app.knowledge.model import Edge, Node


class YamlImporter(GraphImporter):
    """Loads a `{nodes, edges}` YAML document."""

    def load(self, source: str | Path) -> tuple[list[Node], list[Edge]]:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportFormatError("PyYAML is not installed") from exc
        try:
            text = Path(source).read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except (OSError, yaml.YAMLError) as exc:
            raise ImportFormatError(f"Could not read YAML ontology: {exc}") from exc
        return parse_graph_dict(data or {})
