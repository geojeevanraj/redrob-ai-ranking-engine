"""Decision service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile, PersonalInfo
from app.core.exceptions import NotFoundError
from app.decision import DecisionIntelligenceEngine
from app.decision.model import DecisionProfile, Recommendation, ScoreComponent
from app.jobs.schema import JobMetadata, JobProfile
from app.models.candidate import CandidateProfileRecord
from app.models.decision import DecisionRecord
from app.models.job import JobProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.repositories.job import JobRepository
from app.services.decision_service import DecisionService


def sample_decision() -> DecisionProfile:
    return DecisionProfile(
        overall_match_score=0.82,
        overall_confidence=0.7,
        recommendation=Recommendation.STRONG_HIRE,
        weighting_profile="backend_engineer",
        components=[
            ScoreComponent(
                key="required_skill_match", name="Required Skill Match", score=0.9, confidence=0.8
            )
        ],
        provider="gemini",
        model="gemini-1.5-flash",
        timestamp=datetime.now(UTC),
    )


class FakeDecisionEngine:
    def __init__(self, decision: DecisionProfile) -> None:
        self.decision = decision
        self.seen_profile: str | None = None

    async def generate(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        *,
        hidden=None,
        dna=None,
        weighting_profile=None,
    ) -> DecisionProfile:  # type: ignore[no-untyped-def]
        self.seen_profile = weighting_profile
        return self.decision


class FakeRepo:
    def __init__(self, record: object | None = None) -> None:
        self.record = record
        self.stored: dict[uuid.UUID, DecisionRecord] = {}

    async def get(self, _id: uuid.UUID) -> object | None:
        if self.record is not None and getattr(self.record, "id", None) == _id:
            return self.record
        return self.stored.get(_id)

    async def get_latest_for_candidate(self, _id: uuid.UUID) -> None:
        return None

    async def add(self, record: DecisionRecord) -> DecisionRecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.stored[record.id] = record
        return record

    async def list(self, **kwargs: object) -> list[DecisionRecord]:
        return list(self.stored.values())


def candidate_record() -> CandidateProfileRecord:
    return CandidateProfileRecord(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        full_name="Ada",
        email=None,
        extraction_confidence=0.8,
        profile=CandidateProfile(personal_info=PersonalInfo(full_name="Ada")).model_dump(
            mode="json"
        ),
    )


def job_record() -> JobProfileRecord:
    return JobProfileRecord(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        job_title="Backend Engineer",
        company_name="Acme",
        extraction_confidence=0.8,
        profile=JobProfile(job_metadata=JobMetadata(job_title="Backend Engineer")).model_dump(
            mode="json"
        ),
    )


def build_service(
    cand: CandidateProfileRecord | None, jrec: JobProfileRecord | None
) -> tuple[DecisionService, FakeRepo]:
    decision_repo = FakeRepo()
    service = DecisionService(
        cast(AsyncSession, object()),
        engine=cast(DecisionIntelligenceEngine, FakeDecisionEngine(sample_decision())),
        repository=cast(DecisionRepository, decision_repo),
        candidate_repository=cast(CandidateRepository, FakeRepo(cand)),
        job_repository=cast(JobRepository, FakeRepo(jrec)),
        hidden_skill_repository=cast(HiddenSkillRepository, FakeRepo()),
        dna_repository=cast(DNARepository, FakeRepo()),
    )
    return service, decision_repo


async def test_evaluate_persists_decision() -> None:
    cand, jrec = candidate_record(), job_record()
    service, _ = build_service(cand, jrec)
    saved = await service.evaluate(cand.id, jrec.id)
    assert saved.candidate_id == cand.id
    assert saved.job_id == jrec.id
    assert saved.recommendation == "Strong Hire"
    assert saved.overall_match_score == 0.82
    assert saved.decision["weighting_profile"] == "backend_engineer"


async def test_evaluate_missing_candidate_raises() -> None:
    _, jrec = candidate_record(), job_record()
    service, _ = build_service(None, jrec)
    with pytest.raises(NotFoundError):
        await service.evaluate(uuid.uuid4(), jrec.id)


async def test_evaluate_missing_job_raises() -> None:
    cand = candidate_record()
    service, _ = build_service(cand, None)
    with pytest.raises(NotFoundError):
        await service.evaluate(cand.id, uuid.uuid4())


async def test_get_and_list() -> None:
    cand, jrec = candidate_record(), job_record()
    service, _ = build_service(cand, jrec)
    saved = await service.evaluate(cand.id, jrec.id)
    fetched = await service.get(saved.id)
    assert fetched.id == saved.id
    listing = await service.list()
    assert any(r.id == saved.id for r in listing)
