"""Token usage and cost tracking.

Defines the data model and a pluggable tracker interface. Sprint 1.1 ships an
in-memory implementation; analytics/persistence backends can be added later by
implementing `UsageTracker` without touching the manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Estimated USD cost per 1K tokens, keyed by model substring (input, output).
# Local models (Ollama) are treated as free. Values are rough estimates used
# only for relative tracking — not billing.
_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini": (0.000075, 0.0003),  # default for unmatched gemini models
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a call; returns 0.0 for unknown/local models."""
    model_l = model.lower()
    for key, (in_rate, out_rate) in _PRICING_PER_1K.items():
        if key in model_l:
            return (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate
    return 0.0


@dataclass(frozen=True)
class UsageRecord:
    """One recorded LLM call's usage and cost metrics."""

    request_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    response_time_ms: float
    success: bool
    fallback_used: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class UsageTracker(ABC):
    """Contract for usage tracking backends."""

    @abstractmethod
    def record(self, record: UsageRecord) -> None:
        """Persist/record a single usage entry."""

    @abstractmethod
    def all(self) -> list[UsageRecord]:
        """Return all recorded entries (most recent last)."""


class InMemoryUsageTracker(UsageTracker):
    """Simple in-process tracker (default). Not connected to analytics yet."""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    def record(self, record: UsageRecord) -> None:
        self._records.append(record)

    def all(self) -> list[UsageRecord]:
        return list(self._records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self._records)

    @property
    def total_cost(self) -> float:
        return sum(r.estimated_cost for r in self._records)
