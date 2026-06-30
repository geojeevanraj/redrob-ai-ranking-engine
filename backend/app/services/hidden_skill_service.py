"""Hidden skill service — infer + persist evidence-backed hidden skills.

Flow:
    fetch CandidateProfileRecord (Sprint 1.3)
    -> reconstruct CandidateProfile
    -> run Hidden Skill Inference Engine (graph proposes, LLM verifies)
    -> persist HiddenSkillProfileRecord linked to the candidate
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile
from app.core.exceptions import NotFoundError
from app.hidden_skills import HiddenSkillInferenceEngine
from app.models.hidden_skill import HiddenSkillProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.base import BaseService


class HiddenSkillService(BaseService):
    """Coordinates hidden-skill inference and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: HiddenSkillInferenceEngine,
        repository: HiddenSkillRepository | None = None,
        candidate_repository: CandidateRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or HiddenSkillRepository(session)
        self.candidates = candidate_repository or CandidateRepository(session)

    async def infer(self, candidate_id: uuid.UUID) -> HiddenSkillProfileRecord:
        """Infer hidden skills for a candidate and persist the result."""
        candidate = await self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} not found")

        profile = CandidateProfile.model_validate(candidate.profile)
        hidden = await self.engine.infer(profile)

        record = HiddenSkillProfileRecord(
            candidate_id=candidate.id,
            skill_count=len(hidden.skills),
            llm_provider=hidden.provider,
            llm_model=hidden.model,
            profile=hidden.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def get_latest(self, candidate_id: uuid.UUID) -> HiddenSkillProfileRecord:
        record = await self.repo.get_latest_for_candidate(candidate_id)
        if record is None:
            raise NotFoundError(f"No hidden-skill profile found for candidate {candidate_id}")
        return record
