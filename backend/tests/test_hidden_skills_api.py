"""Hidden skill API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.common import get_hidden_skill_service
from app.hidden_skills import HiddenSkillInferenceEngine
from app.main import create_app
from app.repositories.candidate import CandidateRepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.hidden_skill_service import HiddenSkillService
from tests.test_hidden_skills_service import (
    FakeCandidateRepo,
    FakeHiddenEngine,
    FakeHiddenRepo,
    candidate_record,
    sample_hidden,
)


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, uuid.UUID]]:
    record = candidate_record()
    service = HiddenSkillService(
        cast(AsyncSession, object()),
        engine=cast(HiddenSkillInferenceEngine, FakeHiddenEngine(sample_hidden())),
        repository=cast(HiddenSkillRepository, FakeHiddenRepo()),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo(record)),
    )
    app = create_app()
    app.dependency_overrides[get_hidden_skill_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, record.id


async def test_infer_endpoint(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    resp = await client.post(f"/api/v1/candidates/{candidate_id}/infer-skills")
    assert resp.status_code == 201
    body = resp.json()
    assert body["skill_count"] == 1
    skill = body["profile"]["skills"][0]
    assert skill["skill_id"] == "rag"
    assert skill["verified_by_llm"] is True
    assert skill["evidence_nodes"]  # evidence chain present


async def test_infer_unknown_candidate_404(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, _ = ctx
    resp = await client.post(f"/api/v1/candidates/{uuid.uuid4()}/infer-skills")
    assert resp.status_code == 404


async def test_get_hidden_skills(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    await client.post(f"/api/v1/candidates/{candidate_id}/infer-skills")
    resp = await client.get(f"/api/v1/candidates/{candidate_id}/hidden-skills")
    assert resp.status_code == 200
    assert resp.json()["profile"]["skills"][0]["skill_id"] == "rag"


async def test_get_hidden_skills_missing_404(ctx: tuple[AsyncClient, uuid.UUID]) -> None:
    client, candidate_id = ctx
    resp = await client.get(f"/api/v1/candidates/{candidate_id}/hidden-skills")
    assert resp.status_code == 404
