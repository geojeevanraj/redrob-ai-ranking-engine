"""Hidden Skill Inference Engine tests (deterministic core + mocked LLM)."""

from __future__ import annotations

from typing import Any

from app.candidates.schema import CandidateProfile, Skills
from app.hidden_skills import HiddenSkillConfig, HiddenSkillInferenceEngine
from app.knowledge import Edge, KnowledgeGraph, Node, NodeType, RelationshipType, load_seed_graph

graph = load_seed_graph()


def profile_with(*skills: str) -> CandidateProfile:
    return CandidateProfile(skills=Skills(ai_ml=list(skills)))


class FakeResp:
    def __init__(self, data: dict[str, Any]) -> None:
        self.json_data = data
        self.provider = "gemini"
        self.model = "gemini-1.5-flash"


class FakeLLM:
    def __init__(self, verifications: list[dict[str, Any]]) -> None:
        self._v = verifications
        self.calls = 0

    async def generate_json(self, prompt: str, **kwargs: Any) -> FakeResp:
        self.calls += 1
        return FakeResp({"verifications": self._v})


class FakePrompt:
    def get(self, key: str, version: Any = "latest", **values: Any) -> str:
        return "PROMPT"


def make_engine(llm: FakeLLM | None = None, **cfg: Any) -> HiddenSkillInferenceEngine:
    return HiddenSkillInferenceEngine(
        graph, llm or FakeLLM([]), FakePrompt(), config=HiddenSkillConfig(**cfg)
    )


# ── Deterministic propose() ────────────────────────────────
def test_propose_infers_multi_source_skills() -> None:
    engine = make_engine()
    proposals = engine.propose(profile_with("LangChain", "LlamaIndex", "FAISS"))
    ids = {p.skill_id for p in proposals}
    # rag is corroborated by langchain + llamaindex; vector-search by faiss (+rag).
    assert "rag" in ids
    assert "vector-search" in ids
    # explicit skills are never proposed as hidden.
    assert "langchain" not in ids and "faiss" not in ids


def test_alias_resolution_seeds_traversal() -> None:
    engine = make_engine()
    # "k8s" must resolve to kubernetes, whose COMPLEMENTS edge reaches docker.
    proposals = engine.propose(profile_with("k8s"))
    assert "docker" in {p.skill_id for p in proposals}


def test_confidence_scoring_rewards_corroboration() -> None:
    engine = make_engine()
    proposals = {p.skill_id: p for p in engine.propose(profile_with("LangChain", "LlamaIndex"))}
    rag = proposals["rag"]
    # Two independent sources via noisy-OR => ~0.84 (> a single 0.6 path).
    assert rag.confidence > 0.8
    assert len(rag.evidence_paths) == 2


def test_multiple_evidence_paths_enable_inference() -> None:
    engine = make_engine()
    # With both sources, embeddings (depth-2 from each) clears the threshold.
    with_both = {p.skill_id for p in engine.propose(profile_with("LangChain", "LlamaIndex"))}
    assert "embeddings" in with_both


def test_weak_single_evidence_rejected() -> None:
    engine = make_engine()
    # With only LangChain, depth-2 single-source nodes are too weak.
    single = {p.skill_id for p in engine.propose(profile_with("LangChain"))}
    assert "rag" in single  # direct depth-1 strong single edge is allowed
    assert "embeddings" not in single  # depth-2 single source => rejected
    assert "vector-search" not in single


def test_no_explicit_skills_yields_no_proposals() -> None:
    engine = make_engine()
    assert engine.propose(CandidateProfile()) == []


def test_cycle_prevention_terminates() -> None:
    cyclic = KnowledgeGraph.build(
        [
            Node(id="a", name="A", type=NodeType.FRAMEWORK, category="x"),
            Node(id="b", name="B", type=NodeType.FRAMEWORK, category="x"),
        ],
        [
            Edge(source="a", target="b", relationship=RelationshipType.RELATED_TO),
            Edge(source="b", target="a", relationship=RelationshipType.RELATED_TO),
        ],
    )
    engine = HiddenSkillInferenceEngine(
        cyclic, FakeLLM([]), FakePrompt(), config=HiddenSkillConfig(strong_single_threshold=0.5)
    )
    proposals = engine.propose(CandidateProfile(skills=Skills(frameworks=["A"])))
    # Terminates (no infinite loop) and proposes B once.
    assert [p.skill_id for p in proposals] == ["b"]


# ── infer() with LLM verification ──────────────────────────
async def test_infer_keeps_only_verified() -> None:
    llm = FakeLLM(
        [
            {"skill_id": "rag", "verified": True, "reasoning": "supported"},
            {"skill_id": "vector-search", "verified": True, "reasoning": "supported"},
            {"skill_id": "python", "verified": False, "reasoning": "weak"},
        ]
    )
    engine = make_engine(llm)
    result = await engine.infer(profile_with("LangChain", "LlamaIndex", "FAISS"))

    ids = {s.skill_id for s in result.skills}
    assert "rag" in ids
    assert "python" not in ids  # rejected by LLM
    assert all(s.verified_by_llm for s in result.skills)
    assert result.provider == "gemini"
    assert llm.calls == 1


async def test_infer_skips_llm_when_no_proposals() -> None:
    llm = FakeLLM([])
    engine = make_engine(llm)
    result = await engine.infer(CandidateProfile())
    assert result.skills == []
    assert llm.calls == 0  # no LLM call when nothing to verify


async def test_infer_preserves_evidence_chain() -> None:
    llm = FakeLLM([{"skill_id": "rag", "verified": True, "reasoning": "ok"}])
    engine = make_engine(llm)
    result = await engine.infer(profile_with("LangChain", "LlamaIndex"))
    rag = next(s for s in result.skills if s.skill_id == "rag")
    assert rag.evidence_paths  # evidence chain always present
    assert rag.evidence_nodes
