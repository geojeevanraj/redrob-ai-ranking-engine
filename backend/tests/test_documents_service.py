"""Service-level tests (upload, validation, duplicate detection) — no live DB.

Uses an in-memory fake repository and a real local file storage in a tmp dir.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.documents import DocumentIntelligenceEngine
from app.documents.storage import LocalFileStorage
from app.models.document import DocumentRecord
from app.repositories.document import DocumentRepository
from app.services.document_service import DocumentService
from tests.documents_helpers import make_txt


class FakeDocumentRepository:
    """In-memory stand-in for DocumentRepository."""

    def __init__(self) -> None:
        self.by_checksum: dict[str, DocumentRecord] = {}
        self.by_id: dict[uuid.UUID, DocumentRecord] = {}
        self.add_calls = 0

    async def add(self, document: DocumentRecord) -> DocumentRecord:
        self.add_calls += 1
        document.created_at = datetime.now(UTC)
        self.by_checksum[document.checksum] = document
        self.by_id[document.id] = document
        return document

    async def get(self, document_id: uuid.UUID) -> DocumentRecord | None:
        return self.by_id.get(document_id)

    async def get_by_checksum(self, checksum: str) -> DocumentRecord | None:
        return self.by_checksum.get(checksum)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[DocumentRecord]:
        return list(self.by_id.values())[offset : offset + limit]


def build_service(tmp_path: Path, *, max_size_bytes: int = 10 * 1024 * 1024) -> DocumentService:
    repo = FakeDocumentRepository()
    return DocumentService(
        cast(AsyncSession, object()),
        storage=LocalFileStorage(tmp_path),
        engine=DocumentIntelligenceEngine(),
        allowed_extensions=["pdf", "docx", "txt"],
        max_size_bytes=max_size_bytes,
        repository=cast(DocumentRepository, repo),
    )


async def test_upload_success(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    record, duplicate = await service.upload(
        filename="resume.txt",
        content_type="text/plain",
        content=make_txt("A reasonably long English document for testing uploads."),
        document_type="resume",
    )
    assert duplicate is False
    assert record.processing_status == "completed"
    assert record.document_type == "resume"
    # File was written to storage.
    assert Path(record.storage_path).is_file()


async def test_duplicate_detection(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    content = make_txt("Same content uploaded twice should be detected as duplicate.")

    first, dup1 = await service.upload(filename="a.txt", content_type="text/plain", content=content)
    second, dup2 = await service.upload(
        filename="b.txt", content_type="text/plain", content=content
    )

    assert dup1 is False
    assert dup2 is True
    assert first.checksum == second.checksum
    assert cast(FakeDocumentRepository, service.repo).add_calls == 1


async def test_unsupported_extension(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    with pytest.raises(UnsupportedMediaTypeError):
        await service.upload(filename="image.png", content_type="image/png", content=b"x")


async def test_empty_file_rejected(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    with pytest.raises(ValidationError):
        await service.upload(filename="empty.txt", content_type="text/plain", content=b"")


async def test_oversized_file_rejected(tmp_path: Path) -> None:
    service = build_service(tmp_path, max_size_bytes=10)
    with pytest.raises(PayloadTooLargeError):
        await service.upload(filename="big.txt", content_type="text/plain", content=b"x" * 100)


async def test_missing_filename_rejected(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    with pytest.raises(ValidationError):
        await service.upload(filename=None, content_type="text/plain", content=b"data")
