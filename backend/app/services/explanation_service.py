"""Explanation service — explain a decision and compare two decisions.

Flow (generate):
    fetch DecisionRecord -> reconstruct DecisionProfile
    fetch the candidate profile (for richer evidence + gap adjacency)
    -> run Explainability Engine (deterministic build + LLM readability rewrite)
    -> persist ExplanationRecord linked to the decision
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.schema import CandidateProfile
from app.core.exceptions import NotFoundError
from app.decision.model import DecisionProfile
from app.explainability import ComparisonProfile, ExplainabilityEngine
from app.models.decision import DecisionRecord
from app.models.explanation import ExplanationRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.decision import DecisionRepository
from app.repositories.explanation import ExplanationRepository
from app.repositories.job import JobRepository
from app.services.base import BaseService


class ExplanationService(BaseService):
    """Coordinates explanation generation, comparison, and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: ExplainabilityEngine,
        repository: ExplanationRepository | None = None,
        decision_repository: DecisionRepository | None = None,
        candidate_repository: CandidateRepository | None = None,
        job_repository: JobRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or ExplanationRepository(session)
        self.decisions = decision_repository or DecisionRepository(session)
        self.candidates = candidate_repository or CandidateRepository(session)
        self.jobs = job_repository or JobRepository(session)

    async def generate(self, decision_id: uuid.UUID) -> ExplanationRecord:
        decision_record = await self._get_decision(decision_id)
        decision = DecisionProfile.model_validate(decision_record.decision)

        candidate, candidate_name = await self._candidate_context(decision_record)
        job_title = await self._job_title(decision_record)

        explanation = await self.engine.generate(
            decision,
            decision_id=str(decision_record.id),
            candidate=candidate,
            job_title=job_title,
            candidate_name=candidate_name,
        )
        record = ExplanationRecord(
            decision_id=decision_record.id,
            recommendation=explanation.recommendation,
            llm_provider=explanation.provider,
            llm_model=explanation.model,
            explanation=explanation.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def compare(
        self, decision_id_a: uuid.UUID, decision_id_b: uuid.UUID
    ) -> ComparisonProfile:
        a = await self._get_decision(decision_id_a)
        b = await self._get_decision(decision_id_b)
        decision_a = DecisionProfile.model_validate(a.decision)
        decision_b = DecisionProfile.model_validate(b.decision)
        return await self.engine.generate_comparison(
            decision_a, decision_b, decision_a_id=str(a.id), decision_b_id=str(b.id)
        )

    async def get(self, explanation_id: uuid.UUID) -> ExplanationRecord:
        record = await self.repo.get(explanation_id)
        if record is None:
            raise NotFoundError(f"Explanation {explanation_id} not found")
        return record

    # ── Helpers ─────────────────────────────────────────────
    async def _get_decision(self, decision_id: uuid.UUID) -> DecisionRecord:
        record = await self.decisions.get(decision_id)
        if record is None:
            raise NotFoundError(f"Decision {decision_id} not found")
        return record

    async def _candidate_context(
        self, decision_record: DecisionRecord
    ) -> tuple[CandidateProfile | None, str | None]:
        candidate_record = await self.candidates.get(decision_record.candidate_id)
        if candidate_record is None:
            return None, None
        return (
            CandidateProfile.model_validate(candidate_record.profile),
            candidate_record.full_name,
        )

    async def _job_title(self, decision_record: DecisionRecord) -> str | None:
        job_record = await self.jobs.get(decision_record.job_id)
        return job_record.job_title if job_record is not None else None
