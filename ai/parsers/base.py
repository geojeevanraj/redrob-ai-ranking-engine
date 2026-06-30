"""Document parser interface.

A parser extracts plain text (and lightweight structure) from an uploaded
document such as a PDF/DOCX resume or a job description. Concrete parsers are
implemented in a future sprint.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedDocument:
    """Result of parsing a raw document into text."""

    text: str
    # Optional structural hints (sections, page count, etc.).
    metadata: dict[str, object] = field(default_factory=dict)


class DocumentParser(ABC):
    """Contract for raw-document text extraction."""

    @abstractmethod
    async def parse(self, content: bytes, *, content_type: str) -> ParsedDocument:
        """Extract text from raw bytes given a MIME content type."""
