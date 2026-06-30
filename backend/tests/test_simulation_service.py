"""Hiring Simulator tests — reuses the real deterministic engines, no LLM/DB."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile, ExperienceEntry, Skills
from app.core.exceptions import ValidationError
from app.decision import DecisionIntelligenceEngine, load_decision_config
from app.explainability import ExplainabilityEngine
from app.jobs.schema import ExperienceRequirement, JobMetadata, JobProfile
from app.knowledge import load_seed_graph
from app.models.candidate import CandidateProfileRecord
from app.models.job import JobProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.repositories.job import JobRepository
from app.schemas.simulation import SimulationRequest
from app.services.simulation_service import SimulationService

graph = load_seed_graph()


class FakeLLM:
    async def generate_json(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError("simulator must not call the LLM")


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT"


def candidate_record(
    name: str, skills: Skills, *, years: str | None = None
) -> CandidateProfileRecord:
    profile = CandidateProfile(
        skills=skills,
        technology_stack=skills.all_skills(),
        experience=[ExperienceEntry(company="X", role="Eng", duration=years)] if years else [],
    )
    return CandidateProfileRecord(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        full_name=name,
        email=None,
        extraction_confidence=0.8,
        profile=profile.model_dump(mode="json"),
    )


def job_record() -> JobProfileRecord:
    profile = JobProfile(
        job_metadata=JobMetadata(job_title="Backend Engineer"),
        required_skills=["FastAPI", "PostgreSQL"],
        preferred_skills=["Docker"],
        technology_stack=["FastAPI", "PostgreSQL"],
        experience=ExperienceRequirement(minimum_years=2),
    )
    return JobProfileRecord(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        job_title="Backend Engineer",
        company_name="Acme",
        extraction_confidence=0.8,
        profile=profile.model_dump(mode="json"),
    )


class FakeCandidateRepo:
    def __init__(self, records: list[CandidateProfileRecord]) -> None:
        self.records = records

    async def list(self, *, limit: int = 200, offset: int = 0) -> list[CandidateProfileRecord]:
        return self.records[offset : offset + limit]

    async def get(self, cid: uuid.UUID) -> CandidateProfileRecord | None:
        return next((r for r in self.records if r.id == cid), None)


class FakeJobRepo:
    def __init__(self, record: JobProfileRecord) -> None:
        self.record = record

    async def get(self, jid: uuid.UUID) -> JobProfileRecord | None:
        return self.record if self.record.id == jid else None


class FakeLatestRepo:
    async def get_latest_for_candidate(self, cid: uuid.UUID) -> None:
        return None


def build_service(
    records: list[CandidateProfileRecord], job: JobProfileRecord
) -> SimulationService:
    decision_engine = DecisionIntelligenceEngine(
        graph, FakeLLM(), FakePrompt(), config=load_decision_config()
    )
    explain_engine = ExplainabilityEngine(graph, FakeLLM(), FakePrompt())
    return SimulationService(
        cast(AsyncSession, object()),
        decision_engine=decision_engine,
        explainability_engine=explain_engine,
        candidate_repository=cast(CandidateRepository, FakeCandidateRepo(records)),
        job_repository=cast(JobRepository, FakeJobRepo(job)),
        hidden_skill_repository=cast(HiddenSkillRepository, FakeLatestRepo()),
        dna_repository=cast(DNARepository, FakeLatestRepo()),
    )


def setup() -> (
    tuple[SimulationService, JobProfileRecord, CandidateProfileRecord, CandidateProfileRecord]
):
    ada = candidate_record(
        "Ada",
        Skills(frameworks=["FastAPI"], databases=["PostgreSQL"], programming_languages=["Python"]),
        years="3 years",
    )
    bob = candidate_record("Bob", Skills(ai_ml=["LangChain", "RAG", "Embeddings"]))
    job = job_record()
    return build_service([ada, bob], job), job, ada, bob


async def test_baseline_no_overrides_has_zero_deltas() -> None:
    service, job, _, _ = setup()
    result = await service.run(SimulationRequest(job_id=job.id))
    assert len(result.results) == 2
    for r in result.results:
        assert r.delta == 0.0
        assert r.new_rank == r.baseline_rank
    ada = next(r for r in result.results if r.candidate_name == "Ada")
    assert ada.baseline_rank == 1  # backend candidate leads a backend job


async def test_weight_override_uses_simulation_profile() -> None:
    service, job, _, _ = setup()
    result = await service.run(
        SimulationRequest(job_id=job.id, weight_overrides={"required_skill_match": 1.0})
    )
    assert result.weighting_profile == "__simulation__"


async def test_role_profile_change() -> None:
    service, job, _, _ = setup()
    result = await service.run(SimulationRequest(job_id=job.id, role_profile="ai_engineer"))
    assert result.weighting_profile == "ai_engineer"


async def test_skill_change_moves_rankings_directionally() -> None:
    service, job, _, _ = setup()
    result = await service.run(
        SimulationRequest(
            job_id=job.id,
            remove_skills=["FastAPI", "PostgreSQL"],
            add_required=["LangChain", "RAG"],
        )
    )
    bob = next(r for r in result.results if r.candidate_name == "Bob")
    ada = next(r for r in result.results if r.candidate_name == "Ada")
    # Required skills now favor Bob and disfavor Ada — scores move accordingly.
    assert bob.new_score > bob.baseline_score
    assert ada.new_score < ada.baseline_score
    bob_required = next(c for c in bob.component_deltas if c.key == "required_skill_match")
    ada_required = next(c for c in ada.component_deltas if c.key == "required_skill_match")
    assert bob_required.delta > 0
    assert ada_required.delta < 0
    assert bob.new_rank <= bob.baseline_rank  # Bob moved up (or held)


async def test_delta_and_explanation_consistency() -> None:
    service, job, _, _ = setup()
    result = await service.run(SimulationRequest(job_id=job.id, add_required=["Kubernetes"]))
    for r in result.results:
        assert round(r.new_score - r.baseline_score, 4) == r.delta
        for cd in r.component_deltas:
            assert round(cd.new - cd.baseline, 4) == cd.delta
        assert r.explanation.score_breakdown  # explainability reused + present
        assert r.change_reasons


async def test_empty_candidate_set_raises() -> None:
    service, job, _, _ = setup()
    with pytest.raises(ValidationError):
        await service.run(SimulationRequest(job_id=job.id, candidate_ids=[]))
