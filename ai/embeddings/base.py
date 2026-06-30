"""Embedding provider interface.

A provider turns text into a fixed-dimension, unit-normalized vector. Concrete
implementations (e.g. Sentence Transformers) arrive in a future sprint.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# A vector is a list of floats; aliased for readability across the AI package.
Vector = list[float]


class EmbeddingProvider(ABC):
    """Contract for text-embedding backends."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the fixed output dimension of produced vectors."""

    @abstractmethod
    async def embed(self, text: str) -> Vector:
        """Embed a single text into a unit-normalized vector."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Embed many texts (batched) into unit-normalized vectors."""
