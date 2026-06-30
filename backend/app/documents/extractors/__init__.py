"""Text extractors package.

Importing this package self-registers the built-in extractors (PDF, DOCX, TXT)
with the extractor registry.
"""

# Import concrete extractors for their registration side effects.
from app.documents.extractors import docx as _docx  # noqa: F401
from app.documents.extractors import pdf as _pdf  # noqa: F401
from app.documents.extractors import txt as _txt  # noqa: F401
from app.documents.extractors.base import ExtractionResult, TextExtractor
from app.documents.extractors.registry import get_extractor, register_extractor, supported_formats

__all__ = [
    "ExtractionResult",
    "TextExtractor",
    "get_extractor",
    "register_extractor",
    "supported_formats",
]
