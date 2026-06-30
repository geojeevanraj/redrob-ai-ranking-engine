"""Hidden Skill Inference Engine.

Discovers skills that are NOT explicitly listed on a candidate but are strongly
supported by evidence in the Knowledge Graph.

    The Knowledge Graph proposes.  The LLM verifies.

The `propose()` step is fully **deterministic**: it resolves explicit skills to
graph nodes, traverses allowed relationships (with cycle prevention), aggregates
evidence across multiple paths, and computes a graph-based confidence via a
noisy-OR over corroborating sources. Guardrails reject weak/single-thread
evidence. `infer()` then sends the proposals + evidence to the LLM purely for
verification — the LLM may only accept/reject graph-supported inferences, never
invent new evidence. Every accepted skill keeps its full evidence chain.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from app.candidates.schema import CandidateProfile
from app.hidden_skills.model import EvidencePath, EvidenceStep, HiddenSkill, HiddenSkillProfile
from app.knowledge import KnowledgeGraph, NodeType, RelationshipType

_ALLOWED_RELATIONSHIPS: set[RelationshipType] = {
    RelationshipType.RELATED_TO,
    RelationshipType.REQUIRES,
    RelationshipType.PART_OF,
    RelationshipType.COMPLEMENTS,
    RelationshipType.USES,
    RelationshipType.DEPENDENT_ON,
}

# Node types that count as "skills" worth inferring.
_ALLOWED_INFERRED_TYPES: set[NodeType] = {
    NodeType.PROGRAMMING_LANGUAGE,
    NodeType.FRAMEWORK,
    NodeType.LIBRARY,
    NodeType.DATABASE,
    NodeType.CLOUD,
    NodeType.DEVOPS,
    NodeType.AI,
    NodeType.MACHINE_LEARNING,
    NodeType.TOOL,
    NodeType.PLATFORM,
    NodeType.ARCHITECTURE,
    NodeType.METHODOLOGY,
}

_VERIFY_SYSTEM = (
    "You verify proposed skill inferences. Each proposal includes the explicit "
    "skills and the knowledge-graph evidence chain that supports it. Approve a "
    "proposal ONLY if the provided evidence reasonably supports it. You must NOT "
    "invent new evidence or approve anything not grounded in the supplied "
    "evidence. Respond with a single JSON object."
)


@dataclass
class HiddenSkillConfig:
    """Configurable inference thresholds and guardrails."""

    min_confidence: float = 0.5
    max_depth: int = 2
    decay: float = 0.6
    min_sources: int = 2
    strong_single_threshold: float = 0.55
    allowed_relationships: set[RelationshipType] = field(
        default_factory=lambda: set(_ALLOWED_RELATIONSHIPS)
    )
    allowed_inferred_types: set[NodeType] = field(
        default_factory=lambda: set(_ALLOWED_INFERRED_TYPES)
    )


class LLMResponseLike(Protocol):
    json_data: dict[str, Any] | None
    provider: str
    model: str


class LLMManagerLike(Protocol):
    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        temperature: float = ...,
        max_tokens: int | None = ...,
        required_keys: list[str] | None = ...,
    ) -> LLMResponseLike: ...


class PromptManagerLike(Protocol):
    def get(self, key: str, version: int | str = ..., **values: object) -> str: ...


class HiddenSkillError(Exception):
    """Raised when hidden-skill inference cannot complete."""


@dataclass
class _Reach:
    """Best activation + path by which a seed reached a target."""

    activation: float
    path: EvidencePath


class HiddenSkillInferenceEngine:
    """Proposes hidden skills from the graph, then verifies them via the LLM."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        config: HiddenSkillConfig | None = None,
        prompt_key: str = "hidden_skills/verify",
        prompt_version: int | str = "latest",
    ) -> None:
        self.graph = graph
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.config = config or HiddenSkillConfig()
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version

    # ── Deterministic proposal (no LLM) ─────────────────────
    def propose(self, profile: CandidateProfile) -> list[HiddenSkill]:
        """Return graph-supported skill proposals (deterministic, sorted)."""
        explicit_ids, _ = self._resolve_explicit(profile)
        if not explicit_ids:
            return []

        # target_id -> {seed_id -> _Reach}
        evidence: dict[str, dict[str, _Reach]] = {}
        for seed in explicit_ids:
            self._traverse(seed, explicit_ids, evidence)

        proposals: list[HiddenSkill] = []
        for target_id, reaches in evidence.items():
            node = self.graph.get_node(target_id)
            if node is None or node.type not in self.config.allowed_inferred_types:
                continue
            activations = [r.activation for r in reaches.values()]
            confidence = _noisy_or(activations)
            max_single = max(activations)
            distinct = len(reaches)

            passes_guard = (
                distinct >= self.config.min_sources
                or max_single >= self.config.strong_single_threshold
            )
            if not (passes_guard and confidence >= self.config.min_confidence):
                continue

            paths = [r.path for r in reaches.values()]
            evidence_nodes = self._collect_nodes(paths)
            proposals.append(
                HiddenSkill(
                    inferred_skill=node.name,
                    skill_id=target_id,
                    confidence=round(confidence, 3),
                    evidence_nodes=evidence_nodes,
                    evidence_paths=paths,
                    reasoning_summary=self._summary(node.name, reaches),
                    verified_by_llm=False,
                )
            )

        # Deterministic ordering: confidence desc, then id asc.
        proposals.sort(key=lambda s: (-s.confidence, s.skill_id))
        return proposals

    # ── Full inference (proposal + LLM verification) ────────
    async def infer(self, profile: CandidateProfile) -> HiddenSkillProfile:
        """Propose, then keep only LLM-verified skills."""
        proposals = self.propose(profile)
        thresholds = {
            "min_confidence": self.config.min_confidence,
            "max_depth": self.config.max_depth,
            "min_sources": self.config.min_sources,
            "strong_single_threshold": self.config.strong_single_threshold,
        }
        if not proposals:
            return HiddenSkillProfile(skills=[], timestamp=datetime.now(UTC), thresholds=thresholds)

        verifications, provider, model = await self._verify(proposals)

        accepted: list[HiddenSkill] = []
        for proposal in proposals:
            verdict = verifications.get(proposal.skill_id)
            if verdict is None or not verdict.get("verified"):
                continue
            proposal.verified_by_llm = True
            reasoning = verdict.get("reasoning")
            if reasoning:
                proposal.reasoning_summary = f"{proposal.reasoning_summary} LLM: {reasoning}"
            accepted.append(proposal)

        return HiddenSkillProfile(
            skills=accepted,
            provider=provider,
            model=model,
            timestamp=datetime.now(UTC),
            thresholds=thresholds,
        )

    # ── Internals ───────────────────────────────────────────
    def _resolve_explicit(self, profile: CandidateProfile) -> tuple[set[str], dict[str, str]]:
        """Resolve explicit skill terms to graph node ids."""
        terms: list[str] = [
            *profile.skills.all_skills(),
            *profile.technology_stack,
        ]
        for exp in profile.experience:
            terms.extend(exp.technologies)
        for proj in profile.projects:
            terms.extend(proj.technologies)

        ids: set[str] = set()
        names: dict[str, str] = {}
        for term in terms:
            node = self.graph.resolve_alias(term)
            if node is not None:
                ids.add(node.id)
                names[node.id] = node.name
        return ids, names

    def _traverse(
        self,
        seed: str,
        explicit_ids: set[str],
        evidence: dict[str, dict[str, _Reach]],
    ) -> None:
        """BFS from a seed; record best activation/path to each target."""
        visited: set[str] = {seed}
        queue: deque[tuple[str, int, float, list[EvidenceStep]]] = deque([(seed, 0, 1.0, [])])
        while queue:
            node_id, depth, activation, steps = queue.popleft()
            if depth >= self.config.max_depth:
                continue
            for neighbor in self.graph.neighbors(node_id, direction="out"):
                edge = neighbor.edge
                if edge.relationship not in self.config.allowed_relationships:
                    continue
                target = neighbor.node.id
                if target in visited:  # cycle / revisit prevention
                    continue
                visited.add(target)
                new_activation = activation * edge.confidence * self.config.decay
                new_steps = [
                    *steps,
                    EvidenceStep(
                        source=node_id,
                        relationship=edge.relationship.value,
                        target=target,
                    ),
                ]
                if target not in explicit_ids:
                    path = EvidencePath(origin_skill=seed, steps=new_steps)
                    bucket = evidence.setdefault(target, {})
                    existing = bucket.get(seed)
                    if existing is None or new_activation > existing.activation:
                        bucket[seed] = _Reach(activation=new_activation, path=path)
                queue.append((target, depth + 1, new_activation, new_steps))

    def _collect_nodes(self, paths: list[EvidencePath]) -> list[str]:
        nodes: list[str] = []
        for path in paths:
            if path.origin_skill not in nodes:
                nodes.append(path.origin_skill)
            for step in path.steps:
                if step.target not in nodes:
                    nodes.append(step.target)
        return nodes

    def _summary(self, name: str, reaches: dict[str, _Reach]) -> str:
        origins: list[str] = []
        for seed in reaches:
            seed_node = self.graph.get_node(seed)
            origins.append(seed_node.name if seed_node is not None else seed)
        rels = sorted({step.relationship for r in reaches.values() for step in r.path.steps})
        return (
            f"Inferred '{name}' from {len(reaches)} explicit skill(s) "
            f"[{', '.join(origins)}] via {', '.join(rels)} relationship(s)."
        )

    async def _verify(
        self, proposals: list[HiddenSkill]
    ) -> tuple[dict[str, dict[str, Any]], str | None, str | None]:
        payload = [
            {
                "skill_id": p.skill_id,
                "skill_name": p.inferred_skill,
                "confidence": p.confidence,
                "evidence": [self._path_text(path) for path in p.evidence_paths],
            }
            for p in proposals
        ]
        prompt = self.prompts.get(
            self.prompt_key,
            self.prompt_version,
            proposals=json.dumps(payload, ensure_ascii=False),
        )
        response = await self.llm.generate_json(
            prompt,
            system=_VERIFY_SYSTEM,
            temperature=0.0,
            required_keys=["verifications"],
        )
        data = response.json_data or {}
        verifications: dict[str, dict[str, Any]] = {}
        for item in data.get("verifications", []):
            if isinstance(item, dict) and "skill_id" in item:
                verifications[str(item["skill_id"])] = item
        return verifications, response.provider, response.model

    @staticmethod
    def _path_text(path: EvidencePath) -> str:
        if not path.steps:
            return path.origin_skill
        parts = [path.steps[0].source]
        for step in path.steps:
            parts.append(f"-{step.relationship}->{step.target}")
        return "".join(parts)


def _noisy_or(activations: list[float]) -> float:
    """Combine independent evidence activations; more corroboration => higher."""
    product = 1.0
    for activation in activations:
        product *= 1.0 - max(0.0, min(1.0, activation))
    return 1.0 - product
