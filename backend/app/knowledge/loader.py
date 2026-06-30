"""Seed ontology loader.

Loads the bundled seed ontology (data/ontology.json) into a validated
`KnowledgeGraph`. The format is auto-detected from the file extension, so the
seed could be swapped for YAML/CSV without code changes.
"""

from __future__ import annotations

from pathlib import Path

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.importers import get_importer

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_SEED = DATA_DIR / "ontology.json"


def load_graph_from_file(path: str | Path, *, fmt: str | None = None) -> KnowledgeGraph:
    """Load and validate a knowledge graph from an ontology file."""
    p = Path(path)
    resolved_fmt = fmt or p.suffix.lstrip(".").lower()
    importer = get_importer(resolved_fmt)
    nodes, edges = importer.load(p)
    return KnowledgeGraph.build(nodes, edges, validate=True)


def load_seed_graph() -> KnowledgeGraph:
    """Load the bundled seed ontology."""
    return load_graph_from_file(DEFAULT_SEED)
