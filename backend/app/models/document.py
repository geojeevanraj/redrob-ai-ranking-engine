"""Document ORM model.

Persists processed-document metadata, quality metrics, processing status,
checksum, and both raw and clean text. Kept separate from the domain-level
`CanonicalDocument` dataclass (persistence vs. domain concerns).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentRecord(Base):
    """A processed document and its derived intelligence (AI-free)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Metadata ────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Integrity / dedup ───────────────────────────────────
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # ── Language ────────────────────────────────────────────
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    language_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Quality metrics ─────────────────────────────────────
    text_extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    empty_page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    malformed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Processing ──────────────────────────────────────────
    processing_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # ── Content ─────────────────────────────────────────────
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    clean_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
