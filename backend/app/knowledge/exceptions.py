"""Knowledge Graph exceptions."""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base class for knowledge-graph errors."""


class DuplicateNodeError(KnowledgeError):
    """A node with the same id was added twice."""


class NodeNotFoundError(KnowledgeError):
    """A referenced node does not exist."""


class InvalidReferenceError(KnowledgeError):
    """An edge references a node id that does not exist."""


class MissingCategoryError(KnowledgeError):
    """A node is missing its required category."""


class CyclicAliasError(KnowledgeError):
    """ALIAS_OF relationships form a cycle."""


class ImportFormatError(KnowledgeError):
    """An ontology file could not be parsed for the requested format."""
