"""Offline Candidate Ranking Engine (Sprint 9.1).

Batch pipeline that ranks the official Redrob dataset against one job using
ONLY the existing deterministic engines:

    Behavioral Intelligence  (compute)
    Hidden Skill Inference    (propose — deterministic, no LLM)
    Candidate DNA             (compute — deterministic, no LLM)
    Decision Intelligence     (compute — deterministic, no LLM)

No LLM / Gemini function is ever called inside the ranking loop. Candidates are
consumed from a streaming iterator and only a bounded top-N is retained in
memory (heap of size N), so the engine scales to 100k candidates with O(N)
working set. The Knowledge Graph and parsed Job Profile are passed in once and
reused for every candidate (no recomputation).
"""

from __future__ import annotations

import heapq
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import total_ordering
from pathlib import Path

from app.candidates.schema import CandidateProfile
from app.decision import DecisionConfig, DecisionIntelligenceEngine
from app.decision.model import DecisionProfile
from app.dna.engine import CandidateDNAEngine
from app.hidden_skills.engine import HiddenSkillInferenceEngine
from app.hidden_skills.model import HiddenSkillProfile
from app.jobs.schema import JobProfile
from app.ranking.behavioral_engine import BehavioralIntelligenceEngine
from app.ranking.csv_export import (
    build_reasoning,
    collect_matched_skills,
    collect_missing_skills,
)
from app.ranking.schemas import (
    BehavioralProfile,
    JobBehavioralContext,
    RankedCandidate,
    RedrobSignals,
)

_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_CONFIG = _DATA_DIR / "ranking_config.json"
_BEHAVIORAL_KEY = "behavioral_match"


@total_ordering
class _RevStr:
    """String wrapper with reversed ordering (larger string compares smaller).

    Used so the bounded min-heap's root is the *worst* retained candidate under
    the official ordering "score desc, then candidate_id ascending": for equal
    scores the largest candidate_id is evicted first, keeping the smallest ids.
    """

    __slots__ = ("s",)

    def __init__(self, s: str) -> None:
        self.s = s

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _RevStr) and self.s == other.s

    def __lt__(self, other: _RevStr) -> bool:
        return self.s > other.s

    def __hash__(self) -> int:
        return hash(self.s)


@dataclass
class RankingConfig:
    """Externalized ranking parameters (`ranking_config.json`)."""

    top_n: int = 100
    behavioral_match_weight: float = 0.10
    default_role_profile: str | None = None
    reasoning: dict[str, float] = field(default_factory=dict)


def load_ranking_config(path: str | Path = _DEFAULT_CONFIG) -> RankingConfig:
    """Load ranking parameters from JSON (no hardcoded weights)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RankingConfig(
        top_n=int(data.get("top_n", 100)),
        behavioral_match_weight=float(data.get("behavioral_match_weight", 0.10)),
        default_role_profile=data.get("default_role_profile"),
        reasoning={k: float(v) for k, v in data.get("reasoning", {}).items()},
    )


@dataclass
class _Scored:
    """Internal, retained only for survivors of the bounded top-N."""

    seq: int
    candidate_id: str
    candidate_name: str | None
    score: float
    decision: DecisionProfile
    behavioral: BehavioralProfile


class OfflineRankingEngine:
    """Deterministic, compute-only batch ranker over a candidate stream."""

    def __init__(
        self,
        *,
        decision_engine: DecisionIntelligenceEngine,
        hidden_engine: HiddenSkillInferenceEngine,
        dna_engine: CandidateDNAEngine,
        behavioral_engine: BehavioralIntelligenceEngine,
        config: RankingConfig | None = None,
    ) -> None:
        self.config = config or RankingConfig()
        self.hidden = hidden_engine
        self.dna = dna_engine
        self.behavioral = behavioral_engine
        # Derive a decision engine whose profiles include the configurable
        # Behavioral Match weight. The base engine + its config are left intact.
        self.decision = self._with_behavioral_weight(
            decision_engine, self.config.behavioral_match_weight
        )

    @staticmethod
    def _with_behavioral_weight(
        engine: DecisionIntelligenceEngine, weight: float
    ) -> DecisionIntelligenceEngine:
        base = engine.config
        profiles = {
            name: {**weights, _BEHAVIORAL_KEY: weight} for name, weights in base.profiles.items()
        }
        derived = DecisionConfig(
            profiles=profiles,
            thresholds=dict(base.thresholds),
            role_keywords=dict(base.role_keywords),
            semantic_partial_credit=base.semantic_partial_credit,
        )
        return DecisionIntelligenceEngine(engine.graph, engine.llm, engine.prompts, config=derived)

    # ── Single-candidate scoring (deterministic, no LLM) ────
    def score_candidate(
        self,
        candidate: CandidateProfile,
        signals: RedrobSignals,
        job: JobProfile,
        *,
        job_context: JobBehavioralContext | None = None,
        role_profile: str | None = None,
    ) -> tuple[DecisionProfile, BehavioralProfile]:
        behavioral = self.behavioral.compute(signals, job=job_context)
        hidden = HiddenSkillProfile(skills=self.hidden.propose(candidate))
        dna = self.dna.compute(candidate, hidden)
        decision = self.decision.compute(
            candidate,
            job,
            hidden=hidden,
            dna=dna,
            behavioral=behavioral,
            weighting_profile=role_profile,
        )
        return decision, behavioral

    # ── Batch ranking ───────────────────────────────────────
    def rank(
        self,
        candidates: Iterable[tuple[str, CandidateProfile, RedrobSignals]],
        job: JobProfile,
        *,
        job_context: JobBehavioralContext | None = None,
        top_n: int | None = None,
        role_profile: str | None = None,
    ) -> tuple[list[RankedCandidate], int, str]:
        """Rank a candidate stream.

        Returns ``(top_ranked, total_processed, weighting_profile)``. Only a
        bounded heap of ``top_n`` candidates is held in memory.
        """
        n = top_n if top_n is not None else self.config.top_n
        effective_role = role_profile or self.config.default_role_profile
        if job_context is None:
            job_context = self._job_context(job)

        heap: list[tuple[float, _RevStr, int, _Scored]] = []
        total = 0
        weighting_profile = effective_role or "default"
        for candidate_id, profile, signals in candidates:
            decision, behavioral = self.score_candidate(
                profile, signals, job, job_context=job_context, role_profile=effective_role
            )
            if total == 0:
                weighting_profile = decision.weighting_profile
            entry = _Scored(
                seq=total,
                candidate_id=candidate_id,
                candidate_name=profile.personal_info.full_name,
                score=decision.overall_match_score,
                decision=decision,
                behavioral=behavioral,
            )
            self._offer(heap, entry, n)
            total += 1

        survivors = [e[3] for e in heap]
        # Official ordering: score desc, then candidate_id ascending for ties.
        survivors.sort(key=lambda s: s.candidate_id)
        survivors.sort(key=lambda s: s.score, reverse=True)
        ranked = [self._to_ranked(s, rank=i + 1) for i, s in enumerate(survivors)]
        return ranked, total, weighting_profile

    @staticmethod
    def _offer(heap: list[tuple[float, _RevStr, int, _Scored]], entry: _Scored, n: int) -> None:
        """Maintain a min-heap of the best ``n`` entries.

        Heap key ``(score, _RevStr(candidate_id), seq)``: the root is the *worst*
        retained entry (lowest score; among equal scores, the largest
        candidate_id). A new entry replaces the root only when strictly better
        under the official ordering (higher score, or equal score with a smaller
        candidate_id) — reproducible, stable, and submission-compliant.
        """
        if n <= 0:
            return
        key = (entry.score, _RevStr(entry.candidate_id), entry.seq)
        if len(heap) < n:
            heapq.heappush(heap, (key[0], key[1], key[2], entry))
        elif (key[0], key[1], key[2]) > (heap[0][0], heap[0][1], heap[0][2]):
            heapq.heapreplace(heap, (key[0], key[1], key[2], entry))

    def _to_ranked(self, s: _Scored, *, rank: int) -> RankedCandidate:
        reasoning = build_reasoning(
            s.decision,
            s.behavioral,
            max_strength_skills=int(self.config.reasoning.get("max_strength_skills", 4)),
            min_experience_mention_years=self.config.reasoning.get(
                "min_experience_mention_years", 0.5
            ),
            strong_behavioral_threshold=self.config.reasoning.get(
                "strong_behavioral_threshold", 0.70
            ),
        )
        return RankedCandidate(
            candidate_id=s.candidate_id,
            rank=rank,
            score=s.score,
            recommendation=s.decision.recommendation.value,
            candidate_name=s.candidate_name,
            behavioral_score=s.behavioral.overall_score,
            matched_skills=collect_matched_skills(s.decision, limit=8),
            missing_skills=collect_missing_skills(s.decision, limit=4),
            top_behavioral_signals=s.behavioral.top_signals,
            reasoning=reasoning,
        )

    @staticmethod
    def _job_context(job: JobProfile) -> JobBehavioralContext:
        mode = job.job_metadata.work_mode.value if job.job_metadata.work_mode else None
        return JobBehavioralContext(
            salary_min=job.salary.minimum,
            salary_max=job.salary.maximum,
            work_mode=None if mode == "unknown" else mode,
        )
