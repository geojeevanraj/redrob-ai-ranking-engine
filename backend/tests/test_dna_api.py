"""Candidate DNA API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.common import get_dna_service
from app.dna import CandidateDNAEngine
from app.main import create_app
from app.repositories.candidate import CandidateRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.dna_service import DNAService
from tests.test_dna_service import (
    FakeCandidateRepo,
    FakeDNAEngine,
    FakeDNARepo,
    FakeHiddenRepo,
    candidate_record,
    sample_dna,
)


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, uuid.UUID]]:
    record = candidate_record()
    service = DNAService(
        cast(AsyncSession, object()),
        engine=cast(CandidateDNAEngine, FakeDNAEngine(sample_dna())),
        repository=cast(DNARepository, FakeDNARepo()),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo(record)),
        hidden_skill_repository=cast(HiddenSkillRepository, FakeHiddenRepo()),
    )
    app = create_app()
    app.dependency_overrides[get_dna_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, record.id


async def test_generate_dna_endpoint(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    resp = await client.post(f"/api/v1/candidates/{candidate_id}/dna")
    assert resp.status_code == 201
    body = resp.json()
    assert body["overall_focus"] == "Backend Engineer"
    assert body["dna"]["archetypes"][0]["archetype_id"] == "backend_engineer"


async def test_generate_unknown_candidate_404(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, _ = ctx
    resp = await client.post(f"/api/v1/candidates/{uuid.uuid4()}/dna")
    assert resp.status_code == 404


async def test_get_dna(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    await client.post(f"/api/v1/candidates/{candidate_id}/dna")
    resp = await client.get(f"/api/v1/candidates/{candidate_id}/dna")
    assert resp.status_code == 200
    assert resp.json()["top_archetype"] == "Backend Engineer"


async def test_get_dna_missing_404(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    resp = await client.get(f"/api/v1/candidates/{candidate_id}/dna")
    assert resp.status_code == 404
