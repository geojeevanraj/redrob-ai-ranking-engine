"""Explanation API tests (service dependency overridden — no DB/LLM)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.common import get_explanation_service
from app.explainability import ExplainabilityEngine
from app.main import create_app
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.explanation import ExplanationRepository
from app.repositories.job import JobRepository
from app.services.explanation_service import ExplanationService
from tests.test_explanation_service import (
    FakeCandidateRepo,
    FakeDecisionRepo,
    FakeExplainEngine,
    FakeExplanationRepo,
    FakeJobRepo,
    decision_record,
)


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple[AsyncClient, uuid.UUID, uuid.UUID]]:
    a, b = decision_record(), decision_record()
    service = ExplanationService(
        cast(AsyncSession, object()),
        engine=cast(ExplainabilityEngine, FakeExplainEngine()),
        repository=cast(ExplanationRepository, FakeExplanationRepo()),
        decision_repository=cast(DecisionRepository, FakeDecisionRepo({a.id: a, b.id: b})),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo()),
        job_repository=cast(JobRepository, FakeJobRepo()),
    )
    app = create_app()
    app.dependency_overrides[get_explanation_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, a.id, b.id


async def test_generate_endpoint(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, decision_id, _ = ctx
    resp = await client.post(
        "/api/v1/explanations/generate", json={"decision_id": str(decision_id)}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["recommendation"] == "Hire"
    assert body["explanation"]["executive_summary"] == "summary"


async def test_generate_unknown_decision_404(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, _, _ = ctx
    resp = await client.post(
        "/api/v1/explanations/generate", json={"decision_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404


async def test_compare_endpoint(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, a_id, b_id = ctx
    resp = await client.post(
        "/api/v1/explanations/compare",
        json={"decision_id_a": str(a_id), "decision_id_b": str(b_id)},
    )
    assert resp.status_code == 200
    assert resp.json()["comparison"]["winner"] in {"A", "B", "Tie"}


async def test_get_and_roundtrip(ctx: tuple[AsyncClient, uuid.UUID, uuid.UUID]) -> None:
    client, decision_id, _ = ctx
    created = await client.post(
        "/api/v1/explanations/generate", json={"decision_id": str(decision_id)}
    )
    explanation_id = created.json()["id"]
    detail = await client.get(f"/api/v1/explanations/{explanation_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == explanation_id
