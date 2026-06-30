"""Candidate DNA service — compute + persist a candidate's DNA profile.

Flow:
    fetch CandidateProfileRecord (Sprint 1.3)
    -> reconstruct CandidateProfile
    -> fetch latest HiddenSkillProfile if available (Sprint 3.2)
    -> run Candidate DNA Engine (deterministic scoring + LLM verify/summarize)
    -> persist CandidateDNARecord linked to the candidate
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile
from app.core.exceptions import NotFoundError
from app.dna import CandidateDNAEngine
from app.hidden_skills.model import HiddenSkillProfile
from app.models.dna import CandidateDNARecord
from app.repositories.candidate import CandidateRepository
from app.repositories.dna import DNARepository
from app.repositories.hidden_skill import HiddenSkillRepository
from app.services.base import BaseService


class DNAService(BaseService):
    """Coordinates DNA computation and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: CandidateDNAEngine,
        repository: DNARepository | None = None,
        candidate_repository: CandidateRepository | None = None,
        hidden_skill_repository: HiddenSkillRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or DNARepository(session)
        self.candidates = candidate_repository or CandidateRepository(session)
        self.hidden = hidden_skill_repository or HiddenSkillRepository(session)

    async def generate(self, candidate_id: uuid.UUID) -> CandidateDNARecord:
        candidate = await self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} not found")

        profile = CandidateProfile.model_validate(candidate.profile)

        hidden_record = await self.hidden.get_latest_for_candidate(candidate_id)
        hidden = (
            HiddenSkillProfile.model_validate(hidden_record.profile)
            if hidden_record is not None
            else None
        )

        dna = await self.engine.generate(profile, hidden)
        record = CandidateDNARecord(
            candidate_id=candidate.id,
            overall_focus=dna.overall_engineering_focus,
            top_archetype=dna.top_archetypes[0] if dna.top_archetypes else None,
            llm_provider=dna.provider,
            llm_model=dna.model,
            dna=dna.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def get_latest(self, candidate_id: uuid.UUID) -> CandidateDNARecord:
        record = await self.repo.get_latest_for_candidate(candidate_id)
        if record is None:
            raise NotFoundError(f"No DNA profile found for candidate {candidate_id}")
        return record
