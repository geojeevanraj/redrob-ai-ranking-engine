"""API tests for the document upload endpoints (DB dependency overridden)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.common import get_document_service
from app.documents import DocumentIntelligenceEngine
from app.documents.storage import LocalFileStorage
from app.main import create_app
from app.repositories.document import DocumentRepository
from app.services.document_service import DocumentService
from tests.test_documents_service import FakeDocumentRepository


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """App client with a fake-repo-backed DocumentService injected."""
    app = create_app()
    service = DocumentService(
        cast(AsyncSession, object()),
        storage=LocalFileStorage(tmp_path),
        engine=DocumentIntelligenceEngine(),
        allowed_extensions=["pdf", "docx", "txt"],
        max_size_bytes=10 * 1024 * 1024,
        repository=cast(DocumentRepository, FakeDocumentRepository()),
    )
    app.dependency_overrides[get_document_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_upload_endpoint(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "resume.txt",
                b"A long enough English document body for testing.",
                "text/plain",
            )
        },
        data={"document_type": "resume"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["duplicate"] is False
    assert body["document"]["processing_status"] == "completed"
    assert body["document"]["document_type"] == "resume"


async def test_upload_duplicate(client: AsyncClient) -> None:
    payload = {"file": ("a.txt", b"Identical content for duplicate detection test.", "text/plain")}
    first = await client.post("/api/v1/documents/upload", files=payload)
    second = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("b.txt", b"Identical content for duplicate detection test.", "text/plain")},
    )
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


async def test_unsupported_type_returns_415(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("pic.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media_type"


async def test_list_and_get(client: AsyncClient) -> None:
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("notes.txt", b"Document content for list and get checks.", "text/plain")},
    )
    doc_id = upload.json()["document"]["id"]

    listing = await client.get("/api/v1/documents")
    assert listing.status_code == 200
    assert any(d["id"] == doc_id for d in listing.json())

    detail = await client.get(f"/api/v1/documents/{doc_id}")
    assert detail.status_code == 200
    assert "clean_text" in detail.json()


async def test_get_missing_returns_404(client: AsyncClient) -> None:
    import uuid

    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert resp.status_code == 404
