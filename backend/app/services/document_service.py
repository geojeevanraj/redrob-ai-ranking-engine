"""Document service — orchestrates upload validation, storage, processing, and
persistence.

Flow:
    validate (extension / size / non-empty)
    -> checksum (SHA-256)
    -> duplicate detection (by checksum)
    -> run Document Intelligence Engine -> CanonicalDocument
    -> store raw file (configurable location)
    -> persist DocumentRecord
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.documents import CanonicalDocument, DocumentIntelligenceEngine
from app.documents.storage import FileStorage
from app.models.document import DocumentRecord
from app.repositories.document import DocumentRepository
from app.services.base import BaseService


class DocumentService(BaseService):
    """Coordinates the upload + document-intelligence workflow."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: FileStorage,
        engine: DocumentIntelligenceEngine,
        allowed_extensions: list[str],
        max_size_bytes: int,
        repository: DocumentRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.repo = repository or DocumentRepository(session)
        self.storage = storage
        self.engine = engine
        self.allowed_extensions = allowed_extensions
        self.max_size_bytes = max_size_bytes

    async def upload(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        document_type: str = "unknown",
    ) -> tuple[DocumentRecord, bool]:
        """Process and persist an uploaded document.

        Returns the persisted record and a `duplicate` flag. When a document
        with the same checksum already exists, the existing record is returned
        without reprocessing.
        """
        safe_name = (filename or "").strip()
        if not safe_name:
            raise ValidationError("A filename is required")

        extension = self._validate_extension(safe_name)
        self._validate_size(content)

        from app.documents.metadata import compute_checksum

        checksum = compute_checksum(content)
        existing = await self.repo.get_by_checksum(checksum)
        if existing is not None:
            return existing, True

        canonical = self.engine.process(
            content,
            filename=safe_name,
            document_type=document_type,
            mime_type=content_type,
        )
        storage_path = self.storage.save(
            document_id=canonical.id, extension=extension, content=content
        )
        record = self._to_record(canonical, storage_path=storage_path)
        saved = await self.repo.add(record)
        return saved, False

    async def get(self, document_id: uuid.UUID) -> DocumentRecord | None:
        return await self.repo.get(document_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[DocumentRecord]:
        return list(await self.repo.list(limit=limit, offset=offset))

    # ── Validation ──────────────────────────────────────────
    def _validate_extension(self, filename: str) -> str:
        _, _, ext = filename.rpartition(".")
        ext = ext.lower()
        if not ext or ext not in self.allowed_extensions:
            raise UnsupportedMediaTypeError(
                f"Unsupported file type '.{ext}'. Allowed: {self.allowed_extensions}"
            )
        return ext

    def _validate_size(self, content: bytes) -> None:
        if not content:
            raise ValidationError("Uploaded file is empty")
        if len(content) > self.max_size_bytes:
            raise PayloadTooLargeError(f"File exceeds maximum size of {self.max_size_bytes} bytes")

    # ── Mapping ─────────────────────────────────────────────
    @staticmethod
    def _to_record(canonical: CanonicalDocument, *, storage_path: str) -> DocumentRecord:
        meta = canonical.metadata
        return DocumentRecord(
            id=uuid.UUID(canonical.id),
            filename=meta.filename,
            document_type=meta.document_type,
            extension=meta.extension,
            mime_type=meta.mime_type,
            file_size=meta.file_size,
            page_count=meta.page_count,
            char_count=meta.char_count,
            word_count=meta.word_count,
            checksum=meta.checksum,
            language=canonical.language.language,
            language_confidence=canonical.language.confidence,
            text_extraction_confidence=canonical.quality.text_extraction_confidence,
            empty_page_count=canonical.quality.empty_page_count,
            ocr_required=canonical.quality.ocr_required,
            malformed=canonical.quality.malformed,
            processing_status=canonical.processing_status.value,
            storage_path=storage_path,
            raw_text=canonical.raw_text,
            clean_text=canonical.clean_text,
        )
