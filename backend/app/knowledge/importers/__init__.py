"""Ontology importers (JSON / YAML / CSV)."""

from __future__ import annotations

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.importers.base import GraphImporter, parse_graph_dict
from app.knowledge.importers.csv_importer import CsvImporter
from app.knowledge.importers.json_importer import JsonImporter
from app.knowledge.importers.yaml_importer import YamlImporter

_IMPORTERS: dict[str, type[GraphImporter]] = {
    "json": JsonImporter,
    "yaml": YamlImporter,
    "yml": YamlImporter,
    "csv": CsvImporter,
}


def get_importer(fmt: str) -> GraphImporter:
    """Return an importer instance for a format name."""
    importer_cls = _IMPORTERS.get(fmt.lower())
    if importer_cls is None:
        raise ImportFormatError(f"Unsupported ontology format: '{fmt}'")
    return importer_cls()


__all__ = [
    "CsvImporter",
    "GraphImporter",
    "JsonImporter",
    "YamlImporter",
    "get_importer",
    "parse_graph_dict",
]
