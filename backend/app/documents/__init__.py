"""Document Intelligence layer.

Generic, AI-free pipeline that converts uploaded documents into a
`CanonicalDocument` — the input contract for every future AI engine.
"""

from app.documents.engine import DocumentIntelligenceEngine, format_from_filename
from app.documents.model import (
    CanonicalDocument,
    DocumentFormat,
    DocumentMetadata,
    LanguageInfo,
    ProcessingStatus,
    QualityMetrics,
)

__all__ = [
    "CanonicalDocument",
    "DocumentFormat",
    "DocumentIntelligenceEngine",
    "DocumentMetadata",
    "LanguageInfo",
    "ProcessingStatus",
    "QualityMetrics",
    "format_from_filename",
]
