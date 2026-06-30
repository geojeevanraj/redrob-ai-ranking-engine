"""Knowledge Graph data model.

Generic graph primitives (Node, Edge) and the controlled vocabularies for node
types and relationship types. The model is intentionally domain-agnostic so the
same graph can serve Candidate Intelligence, Job Intelligence, and every future
AI engine. Nodes/edges are Pydantic models so import validation and API
serialization come for free.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """Controlled vocabulary of node types."""

    PROGRAMMING_LANGUAGE = "programming_language"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    DATABASE = "database"
    CLOUD = "cloud"
    DEVOPS = "devops"
    AI = "ai"
    MACHINE_LEARNING = "machine_learning"
    TOOL = "tool"
    PLATFORM = "platform"
    CERTIFICATION = "certification"
    METHODOLOGY = "methodology"
    ARCHITECTURE = "architecture"
    DOMAIN = "domain"
    SOFT_SKILL = "soft_skill"
    ROLE = "role"
    INDUSTRY = "industry"


class RelationshipType(str, Enum):
    """Controlled vocabulary of relationship (edge) types."""

    BELONGS_TO = "BELONGS_TO"
    USES = "USES"
    REQUIRES = "REQUIRES"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    ALIAS_OF = "ALIAS_OF"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    COMPLEMENTS = "COMPLEMENTS"
    SIMILAR_TO = "SIMILAR_TO"
    DEPENDENT_ON = "DEPENDENT_ON"


class Node(BaseModel):
    """A generic ontology node (technology, skill, domain, role, …)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: NodeType
    category: str
    aliases: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0"
    confidence: float = 1.0


class Edge(BaseModel):
    """A directed, typed relationship between two nodes."""

    model_config = ConfigDict(extra="ignore")

    source: str
    target: str
    relationship: RelationshipType
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0"
    confidence: float = 1.0

    def key(self) -> tuple[str, str, RelationshipType]:
        """Identity tuple used for de-duplication and deletion."""
        return (self.source, self.target, self.relationship)


class Neighbor(BaseModel):
    """A node reached via an edge (used by neighbor queries)."""

    edge: Edge
    node: Node


class GraphStats(BaseModel):
    """Summary counts for the graph."""

    node_count: int
    edge_count: int
    node_types: dict[str, int]
    relationship_types: dict[str, int]
