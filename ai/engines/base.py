"""AI engine interface.

The architecture defines several engines (Job Intelligence, Candidate
Intelligence, Career Intelligence, Behavioral Intelligence, Decision
Intelligence, Explainable AI). They all share a common shape: take typed input,
produce a typed result carrying a confidence score and provenance. Generic
contract only — no engine logic in Sprint 0.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class EngineResult(Generic[OutputT]):
    """Standard engine output envelope.

    Carries the typed payload plus the confidence and provenance the
    explainability requirements depend on.
    """

    output: OutputT
    confidence: float  # 0.0 - 1.0
    provenance: list[str] = field(default_factory=list)


class AIEngine(ABC, Generic[InputT, OutputT]):
    """Contract shared by all AI engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the engine's identifier (e.g. 'job-intelligence')."""

    @abstractmethod
    async def run(self, payload: InputT) -> EngineResult[OutputT]:
        """Execute the engine on the given input and return a result envelope."""
