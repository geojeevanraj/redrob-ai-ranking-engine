"""Candidate DNA service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile, PersonalInfo
from app.core.exceptions import NotFoundError
from app.dna import CandidateDNAEngine
from app.dna.model import ArchetypeScore, CandidateDNA
from app.hidden_skills.model import HiddenSkillProfile
from app.models.candidate import CandidateProfileRecord
from app.models.dna import CandidateDNARecord
from app.repositories.candidate import CandidateRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.dna_service import DNAService


def sample_dna() -> CandidateDNA:
    return CandidateDNA(
        archetypes=[
            ArchetypeScore(
                archetype="Backend Engineer",
                archetype_id="backend_engineer",
                score=0.9,
                confidence=0.8,
                supporting_skills=["FastAPI"],
            )
        ],
        top_archetypes=["Backend Engineer"],
        overall_engineering_focus="Backend Engineer",
        provider="gemini",
        model="gemini-1.5-flash",
        timestamp=datetime.now(UTC),
    )


class FakeDNAEngine:
    def __init__(self, dna: CandidateDNA) -> None:
        self.dna = dna

    async def generate(
        self, profile: CandidateProfile, hidden: HiddenSkillProfile | None = None
    ) -> CandidateDNA:
        return self.dna


class FakeCandidateRepo:
    def __init__(self, record: CandidateProfileRecord | None) -> None:
        self.record = record

    async def get(self, candidate_id: uuid.UUID) -> CandidateProfileRecord | None:
        if self.record and self.record.id == candidate_id:
            return self.record
        return None


class FakeHiddenRepo:
    async def get_latest_for_candidate(self, candidate_id: uuid.UUID) -> None:
        return None


class FakeDNARepo:
    def __init__(self) -> None:
        self.by_candidate: dict[uuid.UUID, CandidateDNARecord] = {}

    async def add(self, record: CandidateDNARecord) -> CandidateDNARecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.by_candidate[record.candidate_id] = record
        return record

    async def get_latest_for_candidate(self, candidate_id: uuid.UUID) -> CandidateDNARecord | None:
        return self.by_candidate.get(candidate_id)


def candidate_record() -> CandidateProfileRecord:
    profile = CandidateProfile(personal_info=PersonalInfo(full_name="Ada"))
    return CandidateProfileRecord(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        full_name="Ada",
        email=None,
        extraction_confidence=0.8,
        profile=profile.model_dump(mode="json"),
    )


def build_service(record: CandidateProfileRecord | None) -> DNAService:
    return DNAService(
        cast(AsyncSession, object()),
        engine=cast(CandidateDNAEngine, FakeDNAEngine(sample_dna())),
        repository=cast(DNARepository, FakeDNARepo()),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo(record)),
        hidden_skill_repository=cast(HiddenSkillRepository, FakeHiddenRepo()),
    )


async def test_generate_persists_dna() -> None:
    record = candidate_record()
    service = build_service(record)
    saved = await service.generate(record.id)
    assert saved.candidate_id == record.id
    assert saved.overall_focus == "Backend Engineer"
    assert saved.top_archetype == "Backend Engineer"
    assert saved.dna["archetypes"][0]["archetype_id"] == "backend_engineer"


async def test_generate_missing_candidate_raises() -> None:
    service = build_service(None)
    with pytest.raises(NotFoundError):
        await service.generate(uuid.uuid4())


async def test_get_latest() -> None:
    record = candidate_record()
    service = build_service(record)
    await service.generate(record.id)
    latest = await service.get_latest(record.id)
    assert latest.top_archetype == "Backend Engineer"


async def test_get_latest_missing_raises() -> None:
    record = candidate_record()
    service = build_service(record)
    with pytest.raises(NotFoundError):
        await service.get_latest(record.id)
