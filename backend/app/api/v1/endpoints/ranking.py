"""Offline Candidate Ranking endpoint (Sprint 9.1).

POST /ranking/run   rank the Redrob dataset against a stored job (compute-only).

The ranking pipeline is fully deterministic and never calls an LLM. The job
must already be parsed/stored (via the Job Intelligence Engine); ranking reuses
that JobProfile, the Knowledge Graph, Hidden Skills, Candidate DNA, Decision
Intelligence and the new Behavioral Intelligence engines.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import RankingServiceDep
from app.ranking.schemas import RankingRequest, RankingResult

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.post("/run", response_model=RankingResult, summary="Run offline dataset ranking")
async def run_ranking(payload: RankingRequest, service: RankingServiceDep) -> RankingResult:
    return await service.rank_dataset(payload)
