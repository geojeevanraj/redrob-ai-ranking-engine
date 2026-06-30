"""Hidden skill service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile, PersonalInfo
from app.core.exceptions import NotFoundError
from app.hidden_skills import HiddenSkillInferenceEngine
from app.hidden_skills.model import HiddenSkill, HiddenSkillProfile
from app.models.candidate import CandidateProfileRecord
from app.models.hidden_skill import HiddenSkillProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.hidden_skill_service import HiddenSkillService


def sample_hidden() -> HiddenSkillProfile:
    return HiddenSkillProfile(
        skills=[
            HiddenSkill(
                inferred_skill="Retrieval-Augmented Generation",
                skill_id="rag",
                confidence=0.84,
                evidence_nodes=["langchain", "rag"],
                reasoning_summary="Inferred from LangChain.",
                verified_by_llm=True,
            )
        ],
        provider="gemini",
        model="gemini-1.5-flash",
        timestamp=datetime.now(UTC),
    )


class FakeHiddenEngine:
    def __init__(self, profile: HiddenSkillProfile) -> None:
        self.profile = profile

    async def infer(self, profile: CandidateProfile) -> HiddenSkillProfile:
        return self.profile


class FakeCandidateRepo:
    def __init__(self, record: CandidateProfileRecord | None) -> None:
        self.record = record

    async def get(self, candidate_id: uuid.UUID) -> CandidateProfileRecord | None:
        if self.record and self.record.id == candidate_id:
            return self.record
        return None


class FakeHiddenRepo:
    def __init__(self) -> None:
        self.by_candidate: dict[uuid.UUID, HiddenSkillProfileRecord] = {}

    async def add(self, record: HiddenSkillProfileRecord) -> HiddenSkillProfileRecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.by_candidate[record.candidate_id] = record
        return record

    async def get_latest_for_candidate(
        self, candidate_id: uuid.UUID
    ) -> HiddenSkillProfileRecord | None:
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


def build_service(
    record: CandidateProfileRecord | None,
) -> tuple[HiddenSkillService, FakeHiddenRepo]:
    hidden_repo = FakeHiddenRepo()
    service = HiddenSkillService(
        cast(AsyncSession, object()),
        engine=cast(HiddenSkillInferenceEngine, FakeHiddenEngine(sample_hidden())),
        repository=cast(HiddenSkillRepository, hidden_repo),
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo(record)),
    )
    return service, hidden_repo


async def test_infer_persists_profile() -> None:
    record = candidate_record()
    service, _ = build_service(record)

    saved = await service.infer(record.id)
    assert saved.candidate_id == record.id
    assert saved.skill_count == 1
    assert saved.llm_provider == "gemini"
    assert saved.profile["skills"][0]["skill_id"] == "rag"


async def test_infer_missing_candidate_raises() -> None:
    service, _ = build_service(None)
    with pytest.raises(NotFoundError):
        await service.infer(uuid.uuid4())


async def test_get_latest() -> None:
    record = candidate_record()
    service, _ = build_service(record)
    await service.infer(record.id)
    latest = await service.get_latest(record.id)
    assert latest.skill_count == 1


async def test_get_latest_missing_raises() -> None:
    record = candidate_record()
    service, _ = build_service(record)
    with pytest.raises(NotFoundError):
        await service.get_latest(record.id)
