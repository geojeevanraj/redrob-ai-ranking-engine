"""Explainability Engine tests (deterministic build + mocked LLM rewrite)."""

from __future__ import annotations

from typing import Any

from app.candidates.schema import CandidateProfile, ExperienceEntry, ProjectEntry, Skills
from app.decision.model import DecisionProfile, Recommendation, ScoreComponent
from app.explainability import ExplainabilityEngine
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


def engine(llm: FakeLLM | None = None) -> ExplainabilityEngine:
    return ExplainabilityEngine(graph, llm or FakeLLM({}), FakePrompt())


def decision_a() -> DecisionProfile:
    return DecisionProfile(
        overall_match_score=0.72,
        overall_confidence=0.66,
        recommendation=Recommendation.HIRE,
        weighting_profile="backend_engineer",
        components=[
            ScoreComponent(
                key="required_skill_match",
                name="Required Skill Match",
                score=0.8,
                weight=0.25,
                confidence=0.7,
                matched_skills=["FastAPI"],
                missing_skills=["Kubernetes"],
                supporting_evidence=["matched: FastAPI"],
                reasoning_summary="1/2 matched",
            ),
            ScoreComponent(
                key="preferred_skill_match",
                name="Preferred Skill Match",
                score=0.5,
                weight=0.05,
                matched_skills=["Docker"],
                missing_skills=["Terraform"],
            ),
            ScoreComponent(
                key="experience_alignment",
                name="Experience Alignment",
                score=0.3,
                weight=0.12,
                missing_evidence=["1 more years"],
                reasoning_summary="below required",
            ),
            ScoreComponent(
                key="dna_compatibility",
                name="DNA Compatibility",
                score=0.9,
                weight=0.07,
            ),
        ],
        strengths=["Required Skill Match", "DNA Compatibility"],
        gaps=["Experience Alignment"],
    )


def decision_b() -> DecisionProfile:
    return DecisionProfile(
        overall_match_score=0.6,
        overall_confidence=0.6,
        recommendation=Recommendation.CONSIDER,
        weighting_profile="backend_engineer",
        components=[
            ScoreComponent(key="required_skill_match", name="Required Skill Match", score=0.4),
            ScoreComponent(key="preferred_skill_match", name="Preferred Skill Match", score=0.5),
            ScoreComponent(key="experience_alignment", name="Experience Alignment", score=0.7),
            ScoreComponent(key="dna_compatibility", name="DNA Compatibility", score=0.5),
        ],
    )


def candidate() -> CandidateProfile:
    return CandidateProfile(
        skills=Skills(devops=["Docker"]),
        technology_stack=["Docker"],
        projects=[ProjectEntry(title="Infra", technologies=["FastAPI"])],
        experience=[ExperienceEntry(company="Acme", role="Engineer", technologies=["FastAPI"])],
    )


# ── Deterministic build ────────────────────────────────────
def test_build_strengths_and_weaknesses() -> None:
    exp = engine().build(decision_a(), candidate=candidate())
    assert len(exp.strengths) == 2  # required (0.8) + dna (0.9)
    assert len(exp.weaknesses) == 1  # experience (0.3)
    assert exp.recommendation == "Hire"
    assert exp.llm_rewritten is False  # deterministic, no LLM yet


def test_score_breakdown_evidence_linkage() -> None:
    exp = engine().build(decision_a())
    req = next(s for s in exp.score_breakdown if s.component_key == "required_skill_match")
    assert any("FastAPI" in e for e in req.evidence)
    assert any("Kubernetes" in e for e in req.evidence)
    assert len(exp.score_breakdown) == 4


def test_strength_supporting_projects_and_experience() -> None:
    exp = engine().build(decision_a(), candidate=candidate())
    req = next(s for s in exp.strengths if "required" in s.description.lower())
    assert "FastAPI" in req.supporting_skills
    assert "Infra" in req.supporting_projects
    assert any("Acme" in e for e in req.supporting_experience)


def test_skill_gap_analysis_low_difficulty_via_adjacency() -> None:
    exp = engine().build(decision_a(), candidate=candidate())
    kube = next(g for g in exp.skill_gaps if g.skill == "Kubernetes")
    assert kube.importance == "required"
    assert kube.learning_difficulty == "low"  # Docker (held) is adjacent in the graph
    assert "Docker" in kube.adjacency_evidence
    assert kube.estimated_learning_effort == "~2 weeks"
    assert kube.expected_impact > 0


def test_skill_gap_includes_preferred() -> None:
    exp = engine().build(decision_a())
    assert any(g.skill == "Terraform" and g.importance == "preferred" for g in exp.skill_gaps)


def test_weakness_missing_experience() -> None:
    exp = engine().build(decision_a())
    weak = exp.weaknesses[0]
    assert weak.missing_experience == ["1 more years"]


def test_executive_summary_contains_recommendation() -> None:
    exp = engine().build(decision_a(), job_title="Backend Engineer", candidate_name="Ada")
    assert "Ada" in exp.executive_summary
    assert "Hire" in exp.executive_summary
    assert "Backend Engineer" in exp.executive_summary


# ── Comparison ─────────────────────────────────────────────
def test_compare_winner_and_advantages() -> None:
    cmp = engine().compare(decision_a(), decision_b(), decision_a_id="A", decision_b_id="B")
    assert cmp.winner == "A"  # 0.72 > 0.60
    assert any("Required Skill Match" in adv for adv in cmp.advantages_a)
    # B leads experience alignment (0.7 vs 0.3).
    assert any("Experience Alignment" in adv for adv in cmp.advantages_b)
    # Component comparison covers all shared components with a leader.
    assert len(cmp.component_comparison) == 4
    assert {c.leader for c in cmp.component_comparison} <= {"A", "B", "Tie"}


# ── LLM rewrite (readability only) ─────────────────────────
async def test_generate_rewrites_text_without_changing_scores() -> None:
    llm = FakeLLM(
        {
            "executive_summary": "Rewritten summary.",
            "strengths": ["S1", "S2"],
            "weaknesses": ["W1"],
        }
    )
    eng = engine(llm)
    built = eng.build(decision_a(), candidate=candidate())
    generated = await eng.generate(decision_a(), candidate=candidate())

    # Scores/evidence preserved.
    assert [s.score for s in built.score_breakdown] == [s.score for s in generated.score_breakdown]
    assert generated.strengths[0].supporting_skills == built.strengths[0].supporting_skills
    # Text rewritten.
    assert generated.executive_summary == "Rewritten summary."
    assert generated.strengths[0].description == "S1"
    assert generated.llm_rewritten is True
    assert generated.provider == "gemini"
    assert llm.calls == 1


async def test_generate_comparison_rewrites_reasoning() -> None:
    llm = FakeLLM({"reasoning": "Rewritten reasoning."})
    eng = engine(llm)
    cmp = await eng.generate_comparison(decision_a(), decision_b())
    assert cmp.reasoning == "Rewritten reasoning."
    assert cmp.winner == "A"  # unchanged
    assert cmp.llm_rewritten is True
