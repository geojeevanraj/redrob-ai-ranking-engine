"""Decision service — evaluate a candidate against a job and persist the result.

Flow:
    fetch CandidateProfile + latest HiddenSkillProfile + latest CandidateDNA
    fetch JobProfile
    -> run Decision Intelligence Engine (deterministic scoring + LLM verify)
    -> persist DecisionRecord linked to both candidate and job
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile
from app.core.exceptions import NotFoundError
from app.decision import DecisionIntelligenceEngine
from app.dna.model import CandidateDNA
from app.hidden_skills.model import HiddenSkillProfile
from app.jobs.schema import JobProfile
from app.models.decision import DecisionRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.repositories.job import JobRepository
from app.services.base import BaseService


class DecisionService(BaseService):
    """Coordinates candidate-vs-job evaluation and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: DecisionIntelligenceEngine,
        repository: DecisionRepository | None = None,
        candidate_repository: CandidateRepository | None = None,
        job_repository: JobRepository | None = None,
        hidden_skill_repository: HiddenSkillRepository | None = None,
        dna_repository: DNARepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or DecisionRepository(session)
        self.candidates = candidate_repository or CandidateRepository(session)
        self.jobs = job_repository or JobRepository(session)
        self.hidden = hidden_skill_repository or HiddenSkillRepository(session)
        self.dna = dna_repository or DNARepository(session)

    async def evaluate(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        weighting_profile: str | None = None,
    ) -> DecisionRecord:
        candidate_record = await self.candidates.get(candidate_id)
        if candidate_record is None:
            raise NotFoundError(f"Candidate {candidate_id} not found")
        job_record = await self.jobs.get(job_id)
        if job_record is None:
            raise NotFoundError(f"Job {job_id} not found")

        candidate = CandidateProfile.model_validate(candidate_record.profile)
        job = JobProfile.model_validate(job_record.profile)

        hidden_record = await self.hidden.get_latest_for_candidate(candidate_id)
        hidden = (
            HiddenSkillProfile.model_validate(hidden_record.profile)
            if hidden_record is not None
            else None
        )
        dna_record = await self.dna.get_latest_for_candidate(candidate_id)
        dna = CandidateDNA.model_validate(dna_record.dna) if dna_record is not None else None

        decision = await self.engine.generate(
            candidate, job, hidden=hidden, dna=dna, weighting_profile=weighting_profile
        )

        record = DecisionRecord(
            candidate_id=candidate_record.id,
            job_id=job_record.id,
            overall_match_score=decision.overall_match_score,
            recommendation=decision.recommendation.value,
            weighting_profile=decision.weighting_profile,
            llm_provider=decision.provider,
            llm_model=decision.model,
            decision=decision.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def get(self, decision_id: uuid.UUID) -> DecisionRecord:
        record = await self.repo.get(decision_id)
        if record is None:
            raise NotFoundError(f"Decision {decision_id} not found")
        return record

    async def list(
        self,
        *,
        candidate_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DecisionRecord]:
        return list(
            await self.repo.list(
                candidate_id=candidate_id, job_id=job_id, limit=limit, offset=offset
            )
        )
