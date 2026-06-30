"""Document API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentRecord


class QualitySchema(BaseModel):
    """Quality metrics view."""

    text_extraction_confidence: float
    empty_page_count: int
    ocr_required: bool
    malformed: bool


class LanguageSchema(BaseModel):
    """Detected language view."""

    language: str
    confidence: float


class DocumentRead(BaseModel):
    """Summary view of a processed document (no large text fields)."""

    id: str
    filename: str
    document_type: str
    extension: str
    mime_type: str
    file_size: int
    page_count: int
    char_count: int
    word_count: int
    checksum: str
    processing_status: str
    language: LanguageSchema
    quality: QualitySchema
    created_at: datetime


class DocumentDetail(DocumentRead):
    """Full view including cleaned text (raw text omitted from API by default)."""

    clean_text: str


class DocumentUploadResponse(BaseModel):
    """Response for an upload, indicating whether it was a duplicate."""

    document: DocumentRead
    duplicate: bool


def to_read(record: DocumentRecord) -> DocumentRead:
    """Map an ORM record to the summary schema."""
    return DocumentRead(
        id=str(record.id),
        filename=record.filename,
        document_type=record.document_type,
        extension=record.extension,
        mime_type=record.mime_type,
        file_size=record.file_size,
        page_count=record.page_count,
        char_count=record.char_count,
        word_count=record.word_count,
        checksum=record.checksum,
        processing_status=record.processing_status,
        language=LanguageSchema(language=record.language, confidence=record.language_confidence),
        quality=QualitySchema(
            text_extraction_confidence=record.text_extraction_confidence,
            empty_page_count=record.empty_page_count,
            ocr_required=record.ocr_required,
            malformed=record.malformed,
        ),
        created_at=record.created_at,
    )


def to_detail(record: DocumentRecord) -> DocumentDetail:
    """Map an ORM record to the detailed schema (includes clean text)."""
    base = to_read(record)
    return DocumentDetail(**base.model_dump(), clean_text=record.clean_text)
