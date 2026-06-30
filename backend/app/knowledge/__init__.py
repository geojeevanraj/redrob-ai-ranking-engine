"""Knowledge Graph foundation.

A generic, data-driven ontology of technologies, skills, frameworks, domains,
tools, certifications, and roles — reusable by every future AI engine. Stores
and queries relationships only; performs NO inference.
"""

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.loader import load_seed_graph
from app.knowledge.model import Edge, GraphStats, Neighbor, Node, NodeType, RelationshipType

__all__ = [
    "Edge",
    "GraphStats",
    "KnowledgeGraph",
    "Neighbor",
    "Node",
    "NodeType",
    "RelationshipType",
    "load_seed_graph",
]
