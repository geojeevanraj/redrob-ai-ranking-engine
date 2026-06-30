"""CSV ontology importer.

Expects a directory containing `nodes.csv` and `edges.csv`.

nodes.csv columns: id,name,type,category,aliases,synonyms,description
    (aliases/synonyms are '|'-separated; description optional)
edges.csv columns: source,target,relationship,confidence
    (confidence optional)
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.importers.base import GraphImporter
from app.knowledge.model import Edge, Node


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


class CsvImporter(GraphImporter):
    """Loads nodes.csv + edges.csv from a directory."""

    def load(self, source: str | Path) -> tuple[list[Node], list[Edge]]:
        directory = Path(source)
        nodes_path = directory / "nodes.csv"
        edges_path = directory / "edges.csv"
        if not nodes_path.is_file():
            raise ImportFormatError(f"Missing nodes.csv in {directory}")

        nodes: list[Node] = []
        with nodes_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                nodes.append(
                    Node(
                        id=row["id"].strip(),
                        name=row["name"].strip(),
                        type=row["type"].strip(),
                        category=row["category"].strip(),
                        aliases=_split(row.get("aliases")),
                        synonyms=_split(row.get("synonyms")),
                        description=(row.get("description") or "").strip() or None,
                    )
                )

        edges: list[Edge] = []
        if edges_path.is_file():
            with edges_path.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    confidence = row.get("confidence")
                    edges.append(
                        Edge(
                            source=row["source"].strip(),
                            target=row["target"].strip(),
                            relationship=row["relationship"].strip(),
                            confidence=float(confidence) if confidence else 1.0,
                        )
                    )
        return nodes, edges
