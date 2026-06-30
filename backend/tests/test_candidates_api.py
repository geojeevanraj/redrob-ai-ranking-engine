"""Candidate API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates import CandidateIntelligenceEngine
from app.dependencies.common import get_candidate_service
from app.main import create_app
from app.repositories.candidate import CandidateRepository
from app.repositories.document import DocumentRepository
from app.services.candidate_service import CandidateService
from tests.test_candidates_service import (
    FakeCandidateRepo,
    FakeDocumentRepo,
    FakeEngine,
    sample_profile,
)


class APIContext:
    def __init__(self, service: CandidateService, document_id: uuid.UUID) -> None:
        self.service = service
        self.document_id = document_id


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, APIContext]]:
    doc_repo = FakeDocumentRepo()
    doc = doc_repo.add_doc(clean_text="Ada Lovelace resume content")
    service = CandidateService(
        cast(AsyncSession, object()),
        engine=cast(CandidateIntelligenceEngine, FakeEngine(sample_profile())),
        repository=cast(CandidateRepository, FakeCandidateRepo()),
        document_repository=cast(DocumentRepository, doc_repo),
    )

    app = create_app()
    app.dependency_overrides[get_candidate_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, APIContext(service, doc.id)


async def test_parse_endpoint(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, context = ctx
    resp = await client.post(f"/api/v1/candidates/parse/{context.document_id}")
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["profile"]["personal_info"]["email"] == "ada@x.io"


async def test_parse_unknown_document_returns_404(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, _ = ctx
    resp = await client.post(f"/api/v1/candidates/parse/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_list_and_get(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, context = ctx
    created = await client.post(f"/api/v1/candidates/parse/{context.document_id}")
    candidate_id = created.json()["id"]

    listing = await client.get("/api/v1/candidates")
    assert listing.status_code == 200
    assert any(c["id"] == candidate_id for c in listing.json())

    detail = await client.get(f"/api/v1/candidates/{candidate_id}")
    assert detail.status_code == 200
    assert detail.json()["profile"]["personal_info"]["full_name"] == "Ada Lovelace"


async def test_get_missing_returns_404(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, _ = ctx
    resp = await client.get(f"/api/v1/candidates/{uuid.uuid4()}")
    assert resp.status_code == 404
