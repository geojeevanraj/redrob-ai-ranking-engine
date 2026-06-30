"""Importer tests (JSON / YAML / CSV) using tmp fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.knowledge.exceptions import ImportFormatError
from app.knowledge.importers import get_importer

GRAPH = {
    "nodes": [
        {
            "id": "python",
            "name": "Python",
            "type": "programming_language",
            "category": "language",
            "aliases": ["py"],
        },
        {"id": "fastapi", "name": "FastAPI", "type": "framework", "category": "backend"},
    ],
    "edges": [
        {"source": "fastapi", "target": "python", "relationship": "DEPENDENT_ON"},
    ],
}


def test_json_importer(tmp_path: Path) -> None:
    path = tmp_path / "ontology.json"
    path.write_text(json.dumps(GRAPH), encoding="utf-8")
    nodes, edges = get_importer("json").load(path)
    assert {n.id for n in nodes} == {"python", "fastapi"}
    assert edges[0].relationship.value == "DEPENDENT_ON"


def test_yaml_importer(tmp_path: Path) -> None:
    import yaml

    path = tmp_path / "ontology.yaml"
    path.write_text(yaml.safe_dump(GRAPH), encoding="utf-8")
    nodes, edges = get_importer("yaml").load(path)
    assert {n.id for n in nodes} == {"python", "fastapi"}
    assert len(edges) == 1


def test_csv_importer(tmp_path: Path) -> None:
    (tmp_path / "nodes.csv").write_text(
        "id,name,type,category,aliases,synonyms\n"
        "python,Python,programming_language,language,py,\n"
        "fastapi,FastAPI,framework,backend,,\n",
        encoding="utf-8",
    )
    (tmp_path / "edges.csv").write_text(
        "source,target,relationship,confidence\n" "fastapi,python,DEPENDENT_ON,0.9\n",
        encoding="utf-8",
    )
    nodes, edges = get_importer("csv").load(tmp_path)
    assert {n.id for n in nodes} == {"python", "fastapi"}
    assert "py" in next(n for n in nodes if n.id == "python").aliases
    assert edges[0].confidence == 0.9


def test_unknown_format_raises() -> None:
    with pytest.raises(ImportFormatError):
        get_importer("xml")
