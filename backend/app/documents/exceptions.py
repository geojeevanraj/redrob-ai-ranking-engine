"""Document processing exceptions."""

from __future__ import annotations


class DocumentError(Exception):
    """Base class for document processing errors."""


class UnsupportedFormatError(DocumentError):
    """The document format/extension is not supported by any extractor."""


class ExtractionError(DocumentError):
    """Text extraction failed (corrupt/unreadable document)."""
