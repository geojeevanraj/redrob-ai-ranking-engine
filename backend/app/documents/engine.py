"""Document Intelligence Engine.

Orchestrates the generic, AI-free pipeline that turns raw uploaded bytes into a
`CanonicalDocument`:

    validation -> text extraction -> cleaning -> unicode/whitespace/header
    -> page-marker removal -> metadata -> language detection -> quality metrics

The result is the input contract for every future AI engine. No LLM calls.
"""

from __future__ import annotations

from datetime import datetime

from app.documents.cleaning import CleaningPipeline, default_pipeline
from app.documents.exceptions import ExtractionError, UnsupportedFormatError
from app.documents.extractors import get_extractor
from app.documents.extractors.base import ExtractionResult
from app.documents.language import detect_language
from app.documents.metadata import build_metadata
from app.documents.model import (
    CanonicalDocument,
    DocumentFormat,
    LanguageInfo,
    ProcessingStatus,
    QualityMetrics,
)
from app.documents.quality import compute_quality

# Map file extensions to formats. Extend alongside the extractor registry.
_EXTENSION_FORMATS: dict[str, DocumentFormat] = {
    "pdf": DocumentFormat.PDF,
    "docx": DocumentFormat.DOCX,
    "txt": DocumentFormat.TXT,
}


def format_from_filename(filename: str) -> DocumentFormat:
    """Resolve a `DocumentFormat` from a filename extension."""
    _, _, ext = filename.rpartition(".")
    fmt = _EXTENSION_FORMATS.get(ext.lower())
    if fmt is None:
        raise UnsupportedFormatError(f"Unsupported file extension: '.{ext}'")
    return fmt


class DocumentIntelligenceEngine:
    """Reusable, AI-free document processing pipeline."""

    def __init__(self, cleaning_pipeline: CleaningPipeline | None = None) -> None:
        self.cleaning_pipeline = cleaning_pipeline or default_pipeline()

    def process(
        self,
        content: bytes,
        *,
        filename: str,
        document_type: str = "unknown",
        mime_type: str | None = None,
        uploaded_at: datetime | None = None,
    ) -> CanonicalDocument:
        """Run the full pipeline and return a `CanonicalDocument`.

        Extraction failures do not raise — they produce a `FAILED` document
        flagged as malformed so the upload can still be recorded.
        """
        fmt = format_from_filename(filename)
        extractor = get_extractor(fmt)

        try:
            extraction = extractor.extract(content)
        except ExtractionError as exc:
            return self._failed_document(
                content=content,
                filename=filename,
                document_type=document_type,
                fmt=fmt,
                mime_type=mime_type,
                uploaded_at=uploaded_at,
                warning=str(exc),
            )

        clean_text = self.cleaning_pipeline.run(extraction.text)
        metadata = build_metadata(
            filename=filename,
            document_type=document_type,
            fmt=fmt,
            content=content,
            extraction=extraction,
            clean_text=clean_text,
            mime_type=mime_type,
            uploaded_at=uploaded_at,
        )
        quality = compute_quality(extraction, clean_text)
        language = detect_language(clean_text)
        status = ProcessingStatus.FAILED if quality.malformed else ProcessingStatus.COMPLETED

        return CanonicalDocument(
            metadata=metadata,
            quality=quality,
            language=language,
            raw_text=extraction.text,
            clean_text=clean_text,
            processing_status=status,
            warnings=list(extraction.warnings),
        )

    def _failed_document(
        self,
        *,
        content: bytes,
        filename: str,
        document_type: str,
        fmt: DocumentFormat,
        mime_type: str | None,
        uploaded_at: datetime | None,
        warning: str,
    ) -> CanonicalDocument:
        empty = ExtractionResult(text="", page_count=0, page_texts=[])
        metadata = build_metadata(
            filename=filename,
            document_type=document_type,
            fmt=fmt,
            content=content,
            extraction=empty,
            clean_text="",
            mime_type=mime_type,
            uploaded_at=uploaded_at,
        )
        quality = QualityMetrics(
            text_extraction_confidence=0.0,
            empty_page_count=0,
            ocr_required=False,
            malformed=True,
        )
        return CanonicalDocument(
            metadata=metadata,
            quality=quality,
            language=LanguageInfo(language="unknown", confidence=0.0),
            raw_text="",
            clean_text="",
            processing_status=ProcessingStatus.FAILED,
            warnings=[warning],
        )
