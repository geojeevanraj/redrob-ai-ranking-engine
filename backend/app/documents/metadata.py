"""Metadata extraction helpers (filename, sizes, counts, checksum)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.documents.extractors.base import ExtractionResult
from app.documents.model import DocumentFormat, DocumentMetadata

# Canonical MIME types per supported format.
_MIME_BY_FORMAT: dict[DocumentFormat, str] = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentFormat.TXT: "text/plain",
}


def compute_checksum(content: bytes) -> str:
    """Return the SHA-256 hex digest of the content (for dedup + integrity)."""
    return hashlib.sha256(content).hexdigest()


def mime_for_format(fmt: DocumentFormat) -> str:
    """Return the canonical MIME type for a supported format."""
    return _MIME_BY_FORMAT[fmt]


def count_words(text: str) -> int:
    """Whitespace-delimited word count."""
    return len(text.split())


def build_metadata(
    *,
    filename: str,
    document_type: str,
    fmt: DocumentFormat,
    content: bytes,
    extraction: ExtractionResult,
    clean_text: str,
    mime_type: str | None = None,
    uploaded_at: datetime | None = None,
) -> DocumentMetadata:
    """Assemble descriptive metadata for a processed document."""
    return DocumentMetadata(
        filename=filename,
        document_type=document_type,
        extension=fmt.value,
        mime_type=mime_type or mime_for_format(fmt),
        file_size=len(content),
        page_count=extraction.page_count,
        char_count=len(clean_text),
        word_count=count_words(clean_text),
        checksum=compute_checksum(content),
        uploaded_at=uploaded_at or datetime.now(UTC),
    )
