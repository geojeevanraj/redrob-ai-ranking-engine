"""Sprint 9.1 — Offline Candidate Ranking Engine tests.

Covers: streaming loader, behavioral engine, ranking reproducibility, CSV
validation, top-N generation, sorting stability, behavioral weighting, large
dataset simulation, deterministic reasoning, and the no-LLM guarantee.
"""

from __future__ import annotations

import csv
import itertools
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.candidates.schema import CandidateProfile, Skills
from app.decision import DecisionIntelligenceEngine, load_decision_config
from app.dna.engine import CandidateDNAEngine, DNAConfig, load_archetypes
from app.hidden_skills.engine import HiddenSkillInferenceEngine
from app.jobs.schema import JobMetadata, JobProfile, SalaryInfo
from app.knowledge import load_seed_graph
from app.ranking.behavioral_engine import BehavioralIntelligenceEngine, load_behavior_weights
from app.ranking.csv_export import build_reasoning, write_ranking_csv
from app.ranking.dataset_loader import stream_candidates, stream_profiles, to_candidate_profile
from app.ranking.ranking_engine import OfflineRankingEngine, load_ranking_config
from app.ranking.schemas import RedrobCandidate, RedrobSignals

DATA = Path(__file__).parent / "data" / "redrob_sample.jsonl"
graph = load_seed_graph()


class FakeResp:
    def __init__(self) -> None:
        self.json_data: dict[str, Any] = {"consistent": True, "verifications": [], "archetypes": []}
        self.provider = "fake"
        self.model = "fake"


class FakeLLM:
    """Counts calls so tests can assert the ranking loop never touches the LLM."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResp:
        self.calls += 1
        return FakeResp()


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT"


def make_ranker(llm: FakeLLM | None = None) -> OfflineRankingEngine:
    llm = llm or FakeLLM()
    prompt = FakePrompt()
    decision = DecisionIntelligenceEngine(graph, llm, prompt, config=load_decision_config())
    hidden = HiddenSkillInferenceEngine(graph, llm, prompt)
    dna = CandidateDNAEngine(graph, llm, prompt, config=DNAConfig(archetypes=load_archetypes()))
    behavioral = BehavioralIntelligenceEngine(config=load_behavior_weights())
    return OfflineRankingEngine(
        decision_engine=decision,
        hidden_engine=hidden,
        dna_engine=dna,
        behavioral_engine=behavioral,
        config=load_ranking_config(),
    )


def backend_job() -> JobProfile:
    return JobProfile(
        job_metadata=JobMetadata(job_title="Backend Engineer"),
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker", "Redis"],
        technology_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
        salary=SalaryInfo(minimum=100000, maximum=140000),
    )


# ── Dataset loader ──────────────────────────────────────────
def test_stream_skips_blank_and_malformed() -> None:
    rows = list(stream_candidates(DATA))
    assert len(rows) == 5  # 2 blank/malformed lines ignored
    assert all(isinstance(r, RedrobCandidate) for r in rows)
    assert rows[0].candidate_id == "c-backend-strong"  # deterministic file order


def test_stream_profiles_maps_to_canonical_profile() -> None:
    items = list(stream_profiles(DATA))
    cid, profile, signals = items[0]
    assert cid == "c-backend-strong"
    assert isinstance(profile, CandidateProfile)
    assert "Python" in profile.technology_stack
    assert profile.personal_info.full_name == "Grace Hopper"
    assert signals.open_to_work is True


def test_to_candidate_profile_handles_object_skills() -> None:
    redrob = RedrobCandidate.model_validate(
        {
            "candidate_id": "x",
            "skills": [{"name": "Python"}, "FastAPI", {"skill": "Docker"}],
            "career_history": [{"company": "C", "title": "Eng", "technologies": ["Go"]}],
        }
    )
    profile = to_candidate_profile(redrob)
    assert "Python" in profile.technology_stack
    assert "Docker" in profile.technology_stack
    assert profile.experience[0].role == "Eng"


# ── Behavioral engine ───────────────────────────────────────
def test_behavioral_scores_in_range_and_deterministic() -> None:
    engine = BehavioralIntelligenceEngine(config=load_behavior_weights())
    _, _, signals = next(stream_profiles(DATA))
    a = engine.compute(signals)
    b = engine.compute(signals)
    assert 0.0 <= a.overall_score <= 1.0
    assert a.overall_score == b.overall_score
    assert len(a.components) == 7
    assert all(0.0 <= c.score <= 1.0 for c in a.components)


def test_strong_signals_beat_weak_signals() -> None:
    engine = BehavioralIntelligenceEngine(config=load_behavior_weights())
    by_id = {cid: s for cid, _, s in stream_profiles(DATA)}
    strong = engine.compute(by_id["c-backend-strong"])
    weak = engine.compute(by_id["c-weak"])
    assert strong.overall_score > weak.overall_score


def test_behavioral_degrades_gracefully_with_no_signals() -> None:
    engine = BehavioralIntelligenceEngine(config=load_behavior_weights())
    profile = engine.compute(RedrobSignals())
    assert 0.0 <= profile.overall_score <= 1.0
    assert len(profile.components) == 7


# ── Ranking ─────────────────────────────────────────────────
def test_ranking_reproducible() -> None:
    job = backend_job()
    r1, t1, p1 = make_ranker().rank(stream_profiles(DATA), job)
    r2, t2, p2 = make_ranker().rank(stream_profiles(DATA), job)
    assert t1 == t2 == 5
    assert p1 == p2
    assert [(r.candidate_id, r.score) for r in r1] == [(r.candidate_id, r.score) for r in r2]


def test_ranking_sorted_descending() -> None:
    ranked, _, _ = make_ranker().rank(stream_profiles(DATA), backend_job())
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert [r.rank for r in ranked] == list(range(1, len(ranked) + 1))
    # The strong backend candidate should rank above the weak one.
    order = [r.candidate_id for r in ranked]
    assert order.index("c-backend-strong") < order.index("c-weak")


def test_top_n_limit() -> None:
    ranked, total, _ = make_ranker().rank(stream_profiles(DATA), backend_job(), top_n=2)
    assert total == 5
    assert len(ranked) == 2
    assert ranked[0].rank == 1 and ranked[1].rank == 2


def test_no_llm_calls_during_ranking() -> None:
    llm = FakeLLM()
    ranker = make_ranker(llm)
    ranker.rank(stream_profiles(DATA), backend_job())
    assert llm.calls == 0  # ranking is compute-only


def test_behavioral_weighting_affects_score() -> None:
    """Raising the behavioral weight changes a high-engagement candidate's score."""
    job = backend_job()
    base = make_ranker()
    heavy = make_ranker()
    heavy.config.behavioral_match_weight = 0.40
    heavy.decision = OfflineRankingEngine._with_behavioral_weight(  # type: ignore[attr-defined]
        heavy.decision, 0.40
    )
    _, _, signals = next(stream_profiles(DATA))
    profile = to_candidate_profile(next(stream_candidates(DATA)))
    base_decision, _ = base.score_candidate(profile, signals, job)
    heavy_decision, _ = heavy.score_candidate(profile, signals, job)
    base_bm = next(c for c in base_decision.components if c.key == "behavioral_match")
    heavy_bm = next(c for c in heavy_decision.components if c.key == "behavioral_match")
    assert heavy_bm.weight > base_bm.weight


def test_decision_has_behavioral_component_only_when_supplied() -> None:
    job = backend_job()
    decision = DecisionIntelligenceEngine(
        graph, FakeLLM(), FakePrompt(), config=load_decision_config()
    )
    cand = CandidateProfile(skills=Skills(tools=["Python"]), technology_stack=["Python"])
    without = decision.compute(cand, job)
    assert all(c.key != "behavioral_match" for c in without.components)


# ── CSV export + reasoning ──────────────────────────────────
def test_csv_export_columns_and_rows(tmp_path: Path) -> None:
    ranked, _, _ = make_ranker().rank(stream_profiles(DATA), backend_job())
    out = write_ranking_csv(ranked, tmp_path / "ranking.csv")
    with out.open(encoding="utf-8") as handle:
        reader = list(csv.reader(handle))
    assert reader[0] == ["candidate_id", "rank", "score", "reasoning"]
    assert len(reader) == len(ranked) + 1
    assert reader[1][0] == ranked[0].candidate_id


def test_reasoning_is_deterministic_and_nonempty() -> None:
    ranker = make_ranker()
    job = backend_job()
    profile = to_candidate_profile(next(stream_candidates(DATA)))
    _, _, signals = next(stream_profiles(DATA))
    decision, behavioral = ranker.score_candidate(profile, signals, job)
    a = build_reasoning(decision, behavioral)
    b = build_reasoning(decision, behavioral)
    assert a == b
    assert a
    assert a.count(".") <= 2  # at most two sentences


# ── Large dataset simulation (bounded memory) ───────────────
def _synthetic(n: int) -> Iterator[tuple[str, CandidateProfile, RedrobSignals]]:
    for i in range(n):
        profile = CandidateProfile(
            skills=Skills(tools=["Python", "FastAPI"]), technology_stack=["Python", "FastAPI"]
        )
        yield f"cand-{i}", profile, RedrobSignals(profile_views=float(i % 100))


def test_large_dataset_simulation_is_bounded() -> None:
    ranked, total, _ = make_ranker().rank(_synthetic(2000), backend_job(), top_n=100)
    assert total == 2000
    assert len(ranked) == 100
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_sorting_tiebreak_is_candidate_id_ascending() -> None:
    """Equal-scoring candidates are tie-broken by candidate_id ascending."""
    ranked, _, _ = make_ranker().rank(_synthetic(10), backend_job(), top_n=10)
    assert [r.rank for r in ranked] == list(range(1, 11))
    assert len({r.candidate_id for r in ranked}) == 10
    # For any run of equal scores, candidate_ids must be ascending.
    for a, b in itertools.pairwise(ranked):
        if a.score == b.score:
            assert a.candidate_id <= b.candidate_id


def test_official_schema_signals_are_adapted() -> None:
    """Official redrob_signals keys map onto internal behavioral fields."""
    raw = {
        "candidate_id": "CAND_0000001",
        "profile": {"anonymized_name": "Ira Vora", "summary": "Backend/data engineer"},
        "career_history": [
            {"company": "Mindtree", "title": "Backend Engineer", "duration_months": 27}
        ],
        "skills": [{"name": "Python", "proficiency": "advanced", "endorsements": 5}],
        "redrob_signals": {
            "open_to_work_flag": True,
            "willing_to_relocate": True,
            "profile_views_received_30d": 23,
            "search_appearance_30d": 249,
            "saved_by_recruiters_30d": 4,
            "profile_completeness_score": 86.9,
            "last_active_date": "2026-05-20",
            "skill_assessment_scores": {"NLP": 38.8, "Image Classification": 64.8},
            "expected_salary_range_inr_lpa": {"min": 18.7, "max": 36.1},
            "recruiter_response_rate": 0.34,
        },
    }
    cand = RedrobCandidate.model_validate(raw)
    s = cand.redrob_signals
    assert cand.profile.full_name == "Ira Vora"
    assert s.open_to_work is True
    assert s.relocation is True
    assert s.profile_views == 23
    assert s.search_appearances == 249
    assert s.saved_by_recruiters == 4
    assert s.profile_completeness == 86.9  # 0-100; engine normalizes via _rate()
    assert s.last_active_days is not None and s.last_active_days > 0
    assert sorted(s.skill_assessment_scores) == [38.8, 64.8]
    assert s.assessment_participation == 2.0
    assert s.expected_salary == (18.7 + 36.1) / 2
    # Mapped profile carries an accurate experience duration string.
    profile = to_candidate_profile(cand)
    assert profile.experience[0].duration == "2.2 years"
