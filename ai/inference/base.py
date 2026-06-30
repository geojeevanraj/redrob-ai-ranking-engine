"""Inference strategy interface.

Covers the reasoning-style steps in the architecture (e.g. hidden-skill graph
propagation, DNA archetype scoring). A strategy maps evidence to inferred
attributes, each with a confidence and the sources that produced it. Interface
only — no inference logic in Sprint 0.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Inference:
    """A single inferred attribute with traceable provenance."""

    name: str
    confidence: float  # 0.0 - 1.0
    sources: list[str] = field(default_factory=list)


class InferenceStrategy(ABC):
    """Contract for evidence-to-inference transformations."""

    @abstractmethod
    async def infer(self, evidence: list[str]) -> list[Inference]:
        """Produce confidence-scored, provenance-bearing inferences from evidence."""
