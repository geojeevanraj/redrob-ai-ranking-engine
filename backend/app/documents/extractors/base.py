"""Text extractor interface.

Extraction is hidden behind the `TextExtractor` interface so new formats plug
in without touching the engine. Each extractor returns an `ExtractionResult`
carrying the full text plus per-page text (enabling page-aware quality metrics
and header/footer removal).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.documents.model import DocumentFormat


@dataclass
class ExtractionResult:
    """Output of a text extractor."""

    text: str
    page_count: int
    page_texts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def empty_page_count(self) -> int:
        return sum(1 for p in self.page_texts if not p.strip())


class TextExtractor(ABC):
    """Contract for format-specific text extraction."""

    @property
    @abstractmethod
    def document_format(self) -> DocumentFormat:
        """The format this extractor handles."""

    @abstractmethod
    def extract(self, content: bytes) -> ExtractionResult:
        """Extract text from raw document bytes."""
