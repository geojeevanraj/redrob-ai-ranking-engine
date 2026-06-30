"""Job API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.common import get_job_service
from app.jobs import JobIntelligenceEngine
from app.main import create_app
from app.repositories.document import DocumentRepository
from app.repositories.job import JobRepository
from app.services.job_service import JobService
from tests.test_candidates_service import FakeDocumentRepo
from tests.test_jobs_service import FakeJobEngine, FakeJobRepo, sample_profile


class APIContext:
    def __init__(self, service: JobService, document_id: uuid.UUID) -> None:
        self.service = service
        self.document_id = document_id


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, APIContext]]:
    doc_repo = FakeDocumentRepo()
    doc = doc_repo.add_doc(clean_text="We are hiring a backend engineer...")
    service = JobService(
        cast(AsyncSession, object()),
        engine=cast(JobIntelligenceEngine, FakeJobEngine(sample_profile())),
        repository=cast(JobRepository, FakeJobRepo()),
        document_repository=cast(DocumentRepository, doc_repo),
    )

    app = create_app()
    app.dependency_overrides[get_job_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, APIContext(service, doc.id)


async def test_parse_endpoint(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, context = ctx
    resp = await client.post(f"/api/v1/jobs/parse/{context.document_id}")
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_title"] == "Backend Engineer"
    assert body["profile"]["required_skills"] == ["Python"]


async def test_parse_unknown_document_returns_404(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, _ = ctx
    resp = await client.post(f"/api/v1/jobs/parse/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_list_and_get(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, context = ctx
    created = await client.post(f"/api/v1/jobs/parse/{context.document_id}")
    job_id = created.json()["id"]

    listing = await client.get("/api/v1/jobs")
    assert listing.status_code == 200
    assert any(j["id"] == job_id for j in listing.json())

    detail = await client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["profile"]["job_metadata"]["job_title"] == "Backend Engineer"


async def test_get_missing_returns_404(ctx: tuple[AsyncClient, APIContext]) -> None:
    client, _ = ctx
    resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404
