"""Decision Intelligence Engine tests (deterministic scoring + mocked LLM)."""

from __future__ import annotations

from typing import Any

from app.candidates.schema import CandidateProfile, ExperienceEntry, Skills
from app.decision import DecisionConfig, DecisionIntelligenceEngine
from app.decision.model import Recommendation
from app.jobs.schema import EducationRequirement, ExperienceRequirement, JobMetadata, JobProfile
from app.knowledge import load_seed_graph

graph = load_seed_graph()


class FakeResp:
    def __init__(self, data: dict[str, Any]) -> None:
        self.json_data = data
        self.provider = "gemini"
        self.model = "gemini-1.5-flash"


class FakeLLM:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResp:
        self.calls += 1
        return FakeResp(self.data)


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT"


def full_config() -> DecisionConfig:
    from app.decision import load_decision_config

    return load_decision_config()


def single_weight_config() -> DecisionConfig:
    return DecisionConfig(
        profiles={"default": {"required_skill_match": 1.0}},
        thresholds={"strong_hire": 0.8, "hire": 0.65, "consider": 0.45},
        role_keywords={},
        semantic_partial_credit=0.5,
    )


def make_engine(config: DecisionConfig, llm: FakeLLM | None = None) -> DecisionIntelligenceEngine:
    return DecisionIntelligenceEngine(
        graph, llm or FakeLLM({"consistent": True}), FakePrompt(), config=config
    )


def candidate(skills: list[str], **kw: Any) -> CandidateProfile:
    return CandidateProfile(skills=Skills(tools=skills), technology_stack=skills, **kw)


def job(
    *,
    title: str = "Software Engineer",
    required: list[str] | None = None,
    preferred: list[str] | None = None,
    stack: list[str] | None = None,
    min_years: float | None = None,
    edu: list[str] | None = None,
) -> JobProfile:
    return JobProfile(
        job_metadata=JobMetadata(job_title=title),
        required_skills=required or [],
        preferred_skills=preferred or [],
        technology_stack=stack or [],
        experience=ExperienceRequirement(minimum_years=min_years),
        education=EducationRequirement(required=edu or []),
    )


# ── Deterministic scoring ──────────────────────────────────
def test_produces_all_components() -> None:
    engine = make_engine(full_config())
    d = engine.compute(candidate(["Python", "FastAPI"]), job(required=["Python"]))
    keys = {c.key for c in d.components}
    assert keys == {
        "required_skill_match",
        "preferred_skill_match",
        "skill_coverage",
        "technology_stack_match",
        "experience_alignment",
        "project_relevance",
        "hidden_skill_contribution",
        "dna_compatibility",
        "education_alignment",
        "career_progression",
        "knowledge_graph_semantic_match",
    }
    assert 0.0 <= d.overall_match_score <= 1.0


def test_reproducible() -> None:
    engine = make_engine(full_config())
    cand = candidate(["Python", "FastAPI", "PostgreSQL"])
    j = job(title="Backend Engineer", required=["FastAPI", "PostgreSQL"])
    a = engine.compute(cand, j)
    b = engine.compute(cand, j)
    assert a.overall_match_score == b.overall_match_score
    assert [c.score for c in a.components] == [c.score for c in b.components]


def test_role_specific_weighting_selected() -> None:
    engine = make_engine(full_config())
    d = engine.compute(candidate(["Docker"]), job(title="Senior Backend Engineer"))
    assert d.weighting_profile == "backend_engineer"


def test_explicit_weighting_profile_overrides() -> None:
    engine = make_engine(full_config())
    d = engine.compute(
        candidate(["Docker"]), job(title="Backend Engineer"), weighting_profile="devops_engineer"
    )
    assert d.weighting_profile == "devops_engineer"


def test_evidence_matched_and_missing() -> None:
    engine = make_engine(full_config())
    d = engine.compute(candidate(["Python"]), job(required=["Python", "Rust"]))
    req = next(c for c in d.components if c.key == "required_skill_match")
    assert "Python" in req.matched_skills
    assert "Rust" in req.missing_skills


def test_semantic_match_uses_graph_relationship() -> None:
    # Candidate knows FastAPI; job requires Flask (SIMILAR_TO FastAPI in the graph).
    engine = make_engine(full_config())
    d = engine.compute(candidate(["FastAPI"]), job(required=["Flask"]))
    req = next(c for c in d.components if c.key == "required_skill_match")
    assert req.graph_relationships_used  # a relationship was used for partial credit
    assert 0 < req.score < 1


# ── Recommendation thresholds ──────────────────────────────
def test_recommendation_strong_hire() -> None:
    engine = make_engine(single_weight_config())
    d = engine.compute(candidate(["Python", "FastAPI"]), job(required=["Python", "FastAPI"]))
    assert d.overall_match_score == 1.0
    assert d.recommendation is Recommendation.STRONG_HIRE


def test_recommendation_hire() -> None:
    engine = make_engine(single_weight_config())
    d = engine.compute(
        candidate(["Python", "FastAPI"]), job(required=["Python", "FastAPI", "Haskell"])
    )
    assert round(d.overall_match_score, 2) == 0.67
    assert d.recommendation is Recommendation.HIRE


def test_recommendation_consider() -> None:
    engine = make_engine(single_weight_config())
    d = engine.compute(candidate(["Python"]), job(required=["Python", "Haskell"]))
    assert d.overall_match_score == 0.5
    assert d.recommendation is Recommendation.CONSIDER


def test_recommendation_reject() -> None:
    engine = make_engine(single_weight_config())
    d = engine.compute(candidate(["Python"]), job(required=["Haskell", "Erlang"]))
    assert d.overall_match_score == 0.0
    assert d.recommendation is Recommendation.REJECT


def test_configurable_weights_change_overall() -> None:
    cand = candidate(["Python"])  # matches required fully, stack empty
    j = job(required=["Python"])
    high = DecisionConfig(
        profiles={"default": {"required_skill_match": 1.0}},
        thresholds={"strong_hire": 0.8, "hire": 0.65, "consider": 0.45},
        role_keywords={},
    )
    # Weight only career_progression (a weak proxy) -> different overall.
    low = DecisionConfig(
        profiles={"default": {"career_progression": 1.0}},
        thresholds={"strong_hire": 0.8, "hire": 0.65, "consider": 0.45},
        role_keywords={},
    )
    assert make_engine(high).compute(cand, j).overall_match_score == 1.0
    assert make_engine(low).compute(cand, j).overall_match_score < 1.0


def test_experience_alignment() -> None:
    engine = make_engine(full_config())
    cand = candidate(
        ["Python"],
        experience=[ExperienceEntry(company="Acme", role="Engineer", duration="4 years")],
    )
    d = engine.compute(cand, job(required=["Python"], min_years=2))
    exp = next(c for c in d.components if c.key == "experience_alignment")
    assert exp.score == 1.0  # 4 years >= 2 required


# ── LLM verification ───────────────────────────────────────
async def test_generate_verifies_without_changing_scores() -> None:
    llm = FakeLLM(
        {"consistent": True, "summary": "Solid match.", "strengths": ["Skills"], "gaps": ["Exp"]}
    )
    engine = make_engine(full_config(), llm)
    cand = candidate(["Python", "FastAPI", "PostgreSQL"])
    j = job(title="Backend Engineer", required=["FastAPI", "PostgreSQL"])

    computed = engine.compute(cand, j)
    generated = await engine.generate(cand, j)

    assert computed.overall_match_score == generated.overall_match_score
    assert [c.score for c in computed.components] == [c.score for c in generated.components]
    assert generated.llm_verified is True
    assert generated.reasoning_summary == "Solid match."
    assert generated.strengths == ["Skills"]
    assert generated.provider == "gemini"
    assert llm.calls == 1
