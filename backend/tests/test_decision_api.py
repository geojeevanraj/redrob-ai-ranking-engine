"""Decision API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.decision import DecisionIntelligenceEngine
from app.dependencies.common import get_decision_service
from app.main import create_app
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.repositories.job import JobRepository
from app.services.decision_service import DecisionService
from tests.test_decision_service import (
    FakeDecisionEngine,
    FakeRepo,
    candidate_record,
    job_record,
    sample_decision,
)


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, uuid.UUID, uuid.UUID]]:
    cand, jrec = candidate_record(), job_record()
    service = DecisionService(
        cast(AsyncSession, object()),
        engine=cast(DecisionIntelligenceEngine, FakeDecisionEngine(sample_decision())),
        repository=cast(DecisionRepository, FakeRepo()),
        candidate_repository=cast(CandidateRepository, FakeRepo(cand)),
        job_repository=cast(JobRepository, FakeRepo(jrec)),
        hidden_skill_repository=cast(HiddenSkillRepository, FakeRepo()),
        dna_repository=cast(DNARepository, FakeRepo()),
    )
    app = create_app()
    app.dependency_overrides[get_decision_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, cand.id, jrec.id


async def test_evaluate_endpoint(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, candidate_id, job_id = ctx
    resp = await client.post(
        "/api/v1/decisions/evaluate",
        json={"candidate_id": str(candidate_id), "job_id": str(job_id)},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["recommendation"] == "Strong Hire"
    assert body["decision"]["components"][0]["key"] == "required_skill_match"


async def test_evaluate_unknown_candidate_404(
    ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]
) -> None:
    client, _, job_id = ctx
    resp = await client.post(
        "/api/v1/decisions/evaluate",
        json={"candidate_id": str(uuid.uuid4()), "job_id": str(job_id)},
    )
    assert resp.status_code == 404


async def test_list_and_get(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, candidate_id, job_id = ctx
    created = await client.post(
        "/api/v1/decisions/evaluate",
        json={"candidate_id": str(candidate_id), "job_id": str(job_id)},
    )
    decision_id = created.json()["id"]

    listing = await client.get("/api/v1/decisions")
    assert listing.status_code == 200
    assert any(d["id"] == decision_id for d in listing.json())

    detail = await client.get(f"/api/v1/decisions/{decision_id}")
    assert detail.status_code == 200
    assert detail.json()["overall_match_score"] == 0.82


async def test_get_missing_404(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, _, _ = ctx
    resp = await client.get(f"/api/v1/decisions/{uuid.uuid4()}")
    assert resp.status_code == 404
