"""Canonical document model.

The `CanonicalDocument` is the dependency-free output of the Document
Intelligence Engine and the **input contract for every future AI engine**
(resume parsing, job intelligence, etc.). It is intentionally built from plain
dataclasses (no ORM / no pydantic) so it can be shared and serialized freely.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DocumentFormat(str, Enum):
    """Supported document formats. Extend via the extractor registry."""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class ProcessingStatus(str, Enum):
    """Lifecycle status of a processed document."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DocumentMetadata:
    """Descriptive metadata about a document (no AI involved)."""

    filename: str
    document_type: str  # generic category, e.g. "resume" | "job_description" | "unknown"
    extension: str
    mime_type: str
    file_size: int
    page_count: int
    char_count: int
    word_count: int
    checksum: str
    uploaded_at: datetime


@dataclass
class QualityMetrics:
    """Heuristic quality signals about the extraction (no OCR performed)."""

    text_extraction_confidence: float  # 0.0 - 1.0
    empty_page_count: int
    ocr_required: bool  # detection only — flags likely-scanned documents
    malformed: bool


@dataclass
class LanguageInfo:
    """Detected language and confidence. Translation is never performed."""

    language: str  # ISO-639-1 code or "unknown"
    confidence: float  # 0.0 - 1.0


@dataclass
class CanonicalDocument:
    """Clean, normalized representation of an uploaded document."""

    metadata: DocumentMetadata
    quality: QualityMetrics
    language: LanguageInfo
    raw_text: str
    clean_text: str
    processing_status: ProcessingStatus
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    warnings: list[str] = field(default_factory=list)

    @property
    def checksum(self) -> str:
        """Convenience accessor for the content checksum."""
        return self.metadata.checksum
