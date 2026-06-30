"""Extractor registry — the extensibility seam for new formats.

New formats register an extractor via `@register_extractor(DocumentFormat.X)`.
The engine resolves an extractor by format through `get_extractor`, so adding a
format (e.g. RTF, HTML, ODT) requires only a new extractor module.
"""

from __future__ import annotations

from app.documents.exceptions import UnsupportedFormatError
from app.documents.extractors.base import TextExtractor
from app.documents.model import DocumentFormat

_EXTRACTORS: dict[DocumentFormat, TextExtractor] = {}


def register_extractor(fmt: DocumentFormat):  # type: ignore[no-untyped-def]
    """Class decorator registering a `TextExtractor` for a format."""

    def decorator(cls: type[TextExtractor]) -> type[TextExtractor]:
        _EXTRACTORS[fmt] = cls()
        return cls

    return decorator


def get_extractor(fmt: DocumentFormat) -> TextExtractor:
    """Return the registered extractor for a format."""
    extractor = _EXTRACTORS.get(fmt)
    if extractor is None:
        raise UnsupportedFormatError(f"No extractor registered for format '{fmt.value}'")
    return extractor


def supported_formats() -> list[DocumentFormat]:
    """Return the formats with a registered extractor."""
    return sorted(_EXTRACTORS, key=lambda f: f.value)
