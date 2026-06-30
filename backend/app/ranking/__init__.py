"""Offline Candidate Ranking Engine (Sprint 9.1).

Adapts the existing platform to the official Redrob hackathon dataset:

  * `dataset_loader`   — streaming JSONL loader (100k candidates, O(1) memory)
  * `behavioral_engine`— deterministic Behavioral Intelligence (recruiter signals)
  * `ranking_engine`   — batch, compute-only ranking pipeline (NO LLM)
  * `csv_export`       — deterministic top-N CSV (candidate_id, rank, score, reasoning)
  * `service`          — orchestration over the existing engines + DB job profile

This package only *extends* the platform. It reuses the existing
`CandidateProfile`, Hidden Skill, Candidate DNA and Decision Intelligence
engines via their deterministic `compute()` / `propose()` methods. No engine
logic, deterministic scoring, or AI algorithm is modified.
"""

from __future__ import annotations

from app.ranking.behavioral_engine import (
    BehavioralConfig,
    BehavioralIntelligenceEngine,
    load_behavior_weights,
)
from app.ranking.dataset_loader import (
    DatasetError,
    stream_candidates,
    stream_profiles,
    to_candidate_profile,
)
from app.ranking.ranking_engine import (
    OfflineRankingEngine,
    RankingConfig,
    load_ranking_config,
)
from app.ranking.schemas import (
    BehavioralProfile,
    BehavioralSignalScore,
    JobBehavioralContext,
    RankedCandidate,
    RankingRequest,
    RankingResult,
    RedrobCandidate,
    RedrobSignals,
)
from app.ranking.service import RankingService

__all__ = [
    "BehavioralConfig",
    "BehavioralIntelligenceEngine",
    "BehavioralProfile",
    "BehavioralSignalScore",
    "DatasetError",
    "JobBehavioralContext",
    "OfflineRankingEngine",
    "RankedCandidate",
    "RankingConfig",
    "RankingRequest",
    "RankingResult",
    "RankingService",
    "RedrobCandidate",
    "RedrobSignals",
    "load_behavior_weights",
    "load_ranking_config",
    "stream_candidates",
    "stream_profiles",
    "to_candidate_profile",
]
