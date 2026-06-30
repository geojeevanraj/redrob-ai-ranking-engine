"""Candidate DNA Engine tests (deterministic scoring + mocked LLM)."""

from __future__ import annotations

from typing import Any

from app.candidates.schema import CandidateProfile, ExperienceEntry, ProjectEntry, Skills
from app.dna import ArchetypeRule, CandidateDNAEngine, DNAConfig, load_archetypes
from app.knowledge import load_seed_graph

graph = load_seed_graph()


def default_config(**overrides: Any) -> DNAConfig:
    return DNAConfig(archetypes=load_archetypes(), **overrides)


class FakeResp:
    def __init__(self, data: dict[str, Any]) -> None:
        self.json_data = data
        self.provider = "gemini"
        self.model = "gemini-1.5-flash"


class FakeLLM:
    def __init__(self, consistent_ids: list[str]) -> None:
        self._ids = consistent_ids
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResp:
        self.calls += 1
        return FakeResp(
            {
                "archetypes": [
                    {"archetype_id": aid, "consistent": True, "reasoning": f"ok-{aid}"}
                    for aid in self._ids
                ]
            }
        )


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT"


def make_engine(llm: FakeLLM | None = None, config: DNAConfig | None = None) -> CandidateDNAEngine:
    return CandidateDNAEngine(
        graph, llm or FakeLLM([]), FakePrompt(), config=config or default_config()
    )


def backend_profile() -> CandidateProfile:
    return CandidateProfile(
        skills=Skills(
            programming_languages=["Python"],
            frameworks=["FastAPI", "Django"],
            databases=["PostgreSQL"],
        ),
        experience=[ExperienceEntry(company="Acme", role="Backend Dev", technologies=["Django"])],
        projects=[ProjectEntry(title="API Service", technologies=["FastAPI"])],
        technology_stack=["Python", "FastAPI", "Django", "PostgreSQL"],
    )


def ai_profile() -> CandidateProfile:
    return CandidateProfile(
        skills=Skills(ai_ml=["LangChain", "RAG", "Embeddings"]),
        technology_stack=["LangChain", "RAG", "Embeddings"],
    )


# ── Deterministic scoring ──────────────────────────────────
def test_backend_engineer_is_top() -> None:
    dna = make_engine().compute(backend_profile())
    assert dna.overall_engineering_focus == "Backend Engineer"
    assert "Backend Engineer" in dna.top_archetypes
    backend = next(a for a in dna.archetypes if a.archetype_id == "backend_engineer")
    assert backend.score >= 0.6


def test_ai_engineer_is_top() -> None:
    dna = make_engine().compute(ai_profile())
    assert dna.overall_engineering_focus == "AI Engineer"


def test_evidence_aggregation() -> None:
    dna = make_engine().compute(backend_profile())
    backend = next(a for a in dna.archetypes if a.archetype_id == "backend_engineer")
    assert "API Service" in backend.supporting_projects
    assert any("Backend Dev" in e for e in backend.supporting_experience)
    assert backend.supporting_skills  # explicit skills recorded
    assert backend.evidence  # human-readable evidence present


def test_no_unsupported_archetypes() -> None:
    # A profile with a single language only matches a couple of archetypes.
    dna = make_engine().compute(CandidateProfile(technology_stack=["Python"]))
    assert all(a.score > 0 for a in dna.archetypes)
    assert all(a.evidence for a in dna.archetypes)


def test_empty_profile_yields_no_archetypes() -> None:
    dna = make_engine().compute(CandidateProfile())
    assert dna.archetypes == []
    assert dna.overall_engineering_focus == "Undetermined"


def test_configurable_weights_change_score() -> None:
    rule_full = ArchetypeRule(id="x", name="X", keywords={"python": 1.0}, saturation=1.0)
    rule_half = ArchetypeRule(id="x", name="X", keywords={"python": 1.0}, saturation=2.0)
    profile = CandidateProfile(technology_stack=["Python"])

    full = make_engine(config=DNAConfig(archetypes=[rule_full])).compute(profile)
    half = make_engine(config=DNAConfig(archetypes=[rule_half])).compute(profile)

    assert full.archetypes[0].score == 1.0
    assert half.archetypes[0].score == 0.5


def test_confidence_reflects_evidence_volume() -> None:
    rule = ArchetypeRule(id="x", name="X", keywords={"python": 1.0}, saturation=1.0)
    dna = make_engine(config=DNAConfig(archetypes=[rule], confidence_items=5)).compute(
        CandidateProfile(technology_stack=["Python"])
    )
    # One matching term out of confidence_items=5 -> 0.2 confidence.
    assert dna.archetypes[0].confidence == 0.2


# ── generate() with LLM verification ───────────────────────
async def test_generate_sets_verified_without_changing_scores() -> None:
    llm = FakeLLM(["backend_engineer"])
    engine = make_engine(llm)
    profile = backend_profile()

    computed = engine.compute(profile)
    generated = await engine.generate(profile)

    computed_scores = {a.archetype_id: a.score for a in computed.archetypes}
    generated_scores = {a.archetype_id: a.score for a in generated.archetypes}
    assert computed_scores == generated_scores  # LLM never changes scores

    backend = next(a for a in generated.archetypes if a.archetype_id == "backend_engineer")
    assert backend.llm_verified is True
    assert backend.reasoning_summary == "ok-backend_engineer"
    assert generated.provider == "gemini"
    assert llm.calls == 1


async def test_generate_skips_llm_when_no_archetypes() -> None:
    llm = FakeLLM([])
    engine = make_engine(llm)
    await engine.generate(CandidateProfile())
    assert llm.calls == 0
