"""Explanation service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile, PersonalInfo
from app.core.exceptions import NotFoundError
from app.decision.model import DecisionProfile, Recommendation, ScoreComponent
from app.explainability import ComparisonProfile, ExplainabilityEngine
from app.explainability.model import ExplanationProfile
from app.models.candidate import CandidateProfileRecord
from app.models.decision import DecisionRecord
from app.models.explanation import ExplanationRecord
from app.models.job import JobProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.explanation import ExplanationRepository
from app.repositories.job import JobRepository
from app.services.explanation_service import ExplanationService


def decision_profile() -> DecisionProfile:
    return DecisionProfile(
        overall_match_score=0.72,
        overall_confidence=0.66,
        recommendation=Recommendation.HIRE,
        weighting_profile="backend_engineer",
        components=[
            ScoreComponent(key="required_skill_match", name="Required Skill Match", score=0.8)
        ],
    )


def decision_record() -> DecisionRecord:
    return DecisionRecord(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        overall_match_score=0.72,
        recommendation="Hire",
        weighting_profile="backend_engineer",
        decision=decision_profile().model_dump(mode="json"),
    )


class FakeExplainEngine:
    async def generate(self, decision: DecisionProfile, **kw: object) -> ExplanationProfile:
        return ExplanationProfile(
            decision_id=str(kw.get("decision_id")),
            executive_summary="summary",
            recommendation=decision.recommendation.value,
            overall_match_score=decision.overall_match_score,
            provider="gemini",
            model="gemini-1.5-flash",
            timestamp=datetime.now(UTC),
        )

    async def generate_comparison(
        self, a: DecisionProfile, b: DecisionProfile, **kw: object
    ) -> ComparisonProfile:
        return ComparisonProfile(
            decision_a_id=str(kw.get("decision_a_id")),
            decision_b_id=str(kw.get("decision_b_id")),
            overall_a=a.overall_match_score,
            overall_b=b.overall_match_score,
            winner="A" if a.overall_match_score >= b.overall_match_score else "B",
        )


class FakeDecisionRepo:
    def __init__(self, records: dict[uuid.UUID, DecisionRecord]) -> None:
        self.records = records

    async def get(self, decision_id: uuid.UUID) -> DecisionRecord | None:
        return self.records.get(decision_id)


class FakeExplanationRepo:
    def __init__(self) -> None:
        self.stored: dict[uuid.UUID, ExplanationRecord] = {}

    async def add(self, record: ExplanationRecord) -> ExplanationRecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.stored[record.id] = record
        return record

    async def get(self, explanation_id: uuid.UUID) -> ExplanationRecord | None:
        return self.stored.get(explanation_id)


class FakeCandidateRepo:
    async def get(self, _id: uuid.UUID) -> CandidateProfileRecord:
        return CandidateProfileRecord(
            id=_id,
            document_id=uuid.uuid4(),
            full_name="Ada",
            email=None,
            extraction_confidence=0.8,
            profile=CandidateProfile(personal_info=PersonalInfo(full_name="Ada")).model_dump(
                mode="json"
            ),
        )


class FakeJobRepo:
    async def get(self, _id: uuid.UUID) -> JobProfileRecord:
        return JobProfileRecord(
            id=_id,
            document_id=uuid.uuid4(),
            job_title="Backend Engineer",
            company_name="Acme",
            extraction_confidence=0.8,
            profile={},
        )


def build_service(records: dict[uuid.UUID, DecisionRecord]) -> ExplanationService:
    return ExplanationService(
        cast(AsyncSession, object()),
        engine=cast(ExplainabilityEngine, FakeExplainEngine()),
        repository=cast(ExplanationRepository, FakeExplanationRepo()),
        decision_repository=cast(DecisionRepository, FakeDecisionRepo(records)),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo()),
        job_repository=cast(JobRepository, FakeJobRepo()),
    )


async def test_generate_persists_explanation() -> None:
    rec = decision_record()
    service = build_service({rec.id: rec})
    saved = await service.generate(rec.id)
    assert saved.decision_id == rec.id
    assert saved.recommendation == "Hire"
    assert saved.explanation["executive_summary"] == "summary"


async def test_generate_missing_decision_raises() -> None:
    service = build_service({})
    with pytest.raises(NotFoundError):
        await service.generate(uuid.uuid4())


async def test_compare() -> None:
    a, b = decision_record(), decision_record()
    service = build_service({a.id: a, b.id: b})
    comparison = await service.compare(a.id, b.id)
    assert comparison.winner in {"A", "B"}
    assert comparison.decision_a_id == str(a.id)


async def test_get_explanation() -> None:
    rec = decision_record()
    service = build_service({rec.id: rec})
    saved = await service.generate(rec.id)
    fetched = await service.get(saved.id)
    assert fetched.id == saved.id


async def test_get_missing_raises() -> None:
    service = build_service({})
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4())
