"""Offline ranking service.

Orchestrates a batch ranking run over the official Redrob dataset:

  1. load the (already parsed) JobProfile from the database (NO LLM at rank time),
  2. stream candidates from the configured JSONL dataset,
  3. rank them with the deterministic `OfflineRankingEngine` (compute-only),
  4. optionally export the official top-N CSV.

The Job Description itself is processed once by the existing Job Intelligence
Engine in a prior step (it is stored as a JobProfileRecord). This service never
calls an LLM and never persists or mutates candidate evaluations.
"""

from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.decision import DecisionIntelligenceEngine
from app.dna.engine import CandidateDNAEngine
from app.hidden_skills.engine import HiddenSkillInferenceEngine
from app.jobs.schema import JobProfile
from app.ranking.behavioral_engine import BehavioralIntelligenceEngine
from app.ranking.csv_export import write_ranking_csv
from app.ranking.dataset_loader import stream_profiles
from app.ranking.ranking_engine import OfflineRankingEngine, RankingConfig
from app.ranking.schemas import RankingRequest, RankingResult
from app.repositories.job import JobRepository
from app.services.base import BaseService


class RankingService(BaseService):
    """Runs deterministic, compute-only offline rankings."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        decision_engine: DecisionIntelligenceEngine,
        hidden_engine: HiddenSkillInferenceEngine,
        dna_engine: CandidateDNAEngine,
        behavioral_engine: BehavioralIntelligenceEngine,
        ranking_config: RankingConfig,
        default_dataset_path: str | None = None,
        export_dir: str = "./var/rankings",
        job_repository: JobRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = OfflineRankingEngine(
            decision_engine=decision_engine,
            hidden_engine=hidden_engine,
            dna_engine=dna_engine,
            behavioral_engine=behavioral_engine,
            config=ranking_config,
        )
        self.jobs = job_repository or JobRepository(session)
        self.default_dataset_path = default_dataset_path
        self.export_dir = export_dir

    async def rank_dataset(self, req: RankingRequest) -> RankingResult:
        job_record = await self.jobs.get(req.job_id)
        if job_record is None:
            raise NotFoundError(f"Job {req.job_id} not found")
        job = JobProfile.model_validate(job_record.profile)

        dataset_path = req.dataset_path or self.default_dataset_path
        if not dataset_path:
            raise ValidationError(
                "No dataset path provided and RANKING_DATASET_PATH is not configured"
            )
        if not Path(dataset_path).exists():
            raise NotFoundError(f"Dataset not found: {dataset_path}")

        start = time.perf_counter()
        ranked, total, weighting_profile = self.engine.rank(
            stream_profiles(dataset_path),
            job,
            top_n=req.top_n,
            role_profile=req.role_profile,
        )
        elapsed = time.perf_counter() - start

        csv_path: str | None = None
        if req.export_csv:
            target = req.csv_path or str(Path(self.export_dir) / f"ranking_{req.job_id}.csv")
            csv_path = str(write_ranking_csv(ranked, target))

        return RankingResult(
            job_id=req.job_id,
            job_title=job.job_metadata.job_title,
            weighting_profile=weighting_profile,
            total_candidates=total,
            returned=len(ranked),
            top=ranked,
            csv_path=csv_path,
            elapsed_seconds=round(elapsed, 3),
        )
