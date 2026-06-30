"""Explainability Engine.

Transforms a `DecisionProfile` into a transparent, evidence-backed
`ExplanationProfile`, and compares two decisions into a `ComparisonProfile`.

Everything is computed **deterministically** from the decision's own evidence
(score components carry matched/missing skills, graph relationships, reasoning).
The LLM may ONLY rewrite text for readability — it can never change a score,
add evidence, or alter a recommendation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from app.candidates.schema import CandidateProfile
from app.decision.model import DecisionProfile, ScoreComponent
from app.explainability.model import (
    ComparisonProfile,
    ComponentComparison,
    ExplanationProfile,
    ScoreExplanation,
    SkillGap,
    Strength,
    Weakness,
)
from app.knowledge import KnowledgeGraph, NodeType

_STRONG = 0.75
_WEAK = 0.4
_COMPARE_MARGIN = 0.1
_EPS = 1e-9

_EFFORT_BY_DIFFICULTY = {"low": "~2 weeks", "medium": "~6 weeks", "high": "~12 weeks"}
_HARD_TYPES = {NodeType.AI, NodeType.MACHINE_LEARNING, NodeType.ARCHITECTURE}

_REWRITE_SYSTEM = (
    "You improve the readability of a hiring explanation. You must NOT change any "
    "number, score, recommendation, skill name, or piece of evidence. Only rephrase "
    "the provided text to be clearer and more concise. Respond with a single JSON "
    "object preserving all facts."
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


class ExplainabilityEngine:
    """Deterministic explanation builder + LLM readability rewriter."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        prompt_key: str = "explainability/rewrite",
        prompt_version: int | str = "latest",
    ) -> None:
        self.graph = graph
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version

    # ── Deterministic explanation ───────────────────────────
    def build(
        self,
        decision: DecisionProfile,
        *,
        decision_id: str | None = None,
        candidate: CandidateProfile | None = None,
        job_title: str | None = None,
        candidate_name: str | None = None,
    ) -> ExplanationProfile:
        by_key = {c.key: c for c in decision.components}
        candidate_canon = self._candidate_canon(candidate) if candidate else set()

        score_breakdown = [
            ScoreExplanation(
                component_key=c.key,
                name=c.name,
                score=c.score,
                why=c.reasoning_summary,
                evidence=self._component_evidence(c),
            )
            for c in decision.components
        ]

        strengths = [
            self._strength(c, candidate) for c in decision.components if c.score >= _STRONG
        ]
        weaknesses = [self._weakness(c) for c in decision.components if c.score < _WEAK]

        skill_gaps: list[SkillGap] = []
        for key, importance in (
            ("required_skill_match", "required"),
            ("preferred_skill_match", "preferred"),
        ):
            comp = by_key.get(key)
            if comp is None:
                continue
            for skill in comp.missing_skills:
                skill_gaps.append(self._skill_gap(skill, importance, comp, candidate_canon))

        return ExplanationProfile(
            decision_id=decision_id,
            executive_summary=self._summary(decision, job_title, candidate_name),
            recommendation=decision.recommendation.value,
            overall_match_score=decision.overall_match_score,
            overall_confidence=decision.overall_confidence,
            strengths=strengths,
            weaknesses=weaknesses,
            skill_gaps=skill_gaps,
            score_breakdown=score_breakdown,
            timestamp=datetime.now(UTC),
        )

    async def generate(
        self,
        decision: DecisionProfile,
        *,
        decision_id: str | None = None,
        candidate: CandidateProfile | None = None,
        job_title: str | None = None,
        candidate_name: str | None = None,
    ) -> ExplanationProfile:
        explanation = self.build(
            decision,
            decision_id=decision_id,
            candidate=candidate,
            job_title=job_title,
            candidate_name=candidate_name,
        )
        await self._rewrite(explanation)
        return explanation

    # ── Comparison ──────────────────────────────────────────
    def compare(
        self,
        decision_a: DecisionProfile,
        decision_b: DecisionProfile,
        *,
        decision_a_id: str | None = None,
        decision_b_id: str | None = None,
    ) -> ComparisonProfile:
        by_key_b = {c.key: c for c in decision_b.components}
        comparison: list[ComponentComparison] = []
        advantages_a: list[str] = []
        advantages_b: list[str] = []

        for ca in decision_a.components:
            cb = by_key_b.get(ca.key)
            if cb is None:
                continue
            if ca.score > cb.score + _EPS:
                leader = "A"
            elif cb.score > ca.score + _EPS:
                leader = "B"
            else:
                leader = "Tie"
            comparison.append(
                ComponentComparison(
                    key=ca.key, name=ca.name, score_a=ca.score, score_b=cb.score, leader=leader
                )
            )
            diff = ca.score - cb.score
            label = f"{ca.name}: {ca.score:.2f} vs {cb.score:.2f}"
            if diff >= _COMPARE_MARGIN:
                advantages_a.append(label)
            elif -diff >= _COMPARE_MARGIN:
                advantages_b.append(label)

        if decision_a.overall_match_score > decision_b.overall_match_score + _EPS:
            winner = "A"
        elif decision_b.overall_match_score > decision_a.overall_match_score + _EPS:
            winner = "B"
        else:
            winner = "Tie"

        reasoning = (
            f"A scores {decision_a.overall_match_score:.2f} "
            f"({decision_a.recommendation.value}); B scores "
            f"{decision_b.overall_match_score:.2f} ({decision_b.recommendation.value}). "
            f"A leads in {len(advantages_a)} component(s), B in {len(advantages_b)}. "
            f"Winner: {winner}."
        )

        return ComparisonProfile(
            decision_a_id=decision_a_id,
            decision_b_id=decision_b_id,
            overall_a=decision_a.overall_match_score,
            overall_b=decision_b.overall_match_score,
            winner=winner,
            advantages_a=advantages_a,
            advantages_b=advantages_b,
            disadvantages_a=advantages_b,
            disadvantages_b=advantages_a,
            component_comparison=comparison,
            reasoning=reasoning,
            timestamp=datetime.now(UTC),
        )

    async def generate_comparison(
        self,
        decision_a: DecisionProfile,
        decision_b: DecisionProfile,
        *,
        decision_a_id: str | None = None,
        decision_b_id: str | None = None,
    ) -> ComparisonProfile:
        comparison = self.compare(
            decision_a, decision_b, decision_a_id=decision_a_id, decision_b_id=decision_b_id
        )
        await self._rewrite_comparison(comparison)
        return comparison

    # ── Internals ───────────────────────────────────────────
    def _candidate_canon(self, candidate: CandidateProfile) -> set[str]:
        terms = [*candidate.skills.all_skills(), *candidate.technology_stack]
        for exp in candidate.experience:
            terms.extend(exp.technologies)
        for proj in candidate.projects:
            terms.extend(proj.technologies)
        result: set[str] = set()
        for term in terms:
            node = self.graph.resolve_alias(term)
            result.add(node.id if node else term.strip().lower())
        return result

    @staticmethod
    def _component_evidence(c: ScoreComponent) -> list[str]:
        evidence = list(c.supporting_evidence)
        if c.matched_skills:
            evidence.append(f"matched skills: {', '.join(c.matched_skills)}")
        if c.missing_skills:
            evidence.append(f"missing skills: {', '.join(c.missing_skills)}")
        evidence.extend(f"graph: {rel}" for rel in c.graph_relationships_used)
        return evidence

    def _strength(self, c: ScoreComponent, candidate: CandidateProfile | None) -> Strength:
        matched = self._canon_list(c.matched_skills)
        projects: list[str] = []
        experience: list[str] = []
        if candidate is not None and matched:
            for proj in candidate.projects:
                if matched & self._canon_list(proj.technologies):
                    projects.append(proj.title or "Untitled project")
            for exp in candidate.experience:
                if matched & self._canon_list(exp.technologies):
                    experience.append(f"{exp.role or '?'} @ {exp.company or '?'}")
        return Strength(
            description=f"Strong {c.name.lower()} (score {c.score:.2f}).",
            evidence=self._component_evidence(c),
            supporting_skills=c.matched_skills,
            supporting_projects=sorted(set(projects)),
            supporting_experience=sorted(set(experience)),
        )

    def _canon_list(self, terms: list[str]) -> set[str]:
        result: set[str] = set()
        for term in terms:
            node = self.graph.resolve_alias(term)
            result.add(node.id if node else term.strip().lower())
        return result

    @staticmethod
    def _weakness(c: ScoreComponent) -> Weakness:
        missing_experience = [e for e in c.missing_evidence if "year" in e.lower()]
        return Weakness(
            description=f"Limited {c.name.lower()} (score {c.score:.2f}).",
            missing_evidence=c.missing_evidence,
            missing_skills=c.missing_skills,
            missing_experience=missing_experience,
        )

    def _skill_gap(
        self, skill: str, importance: str, comp: ScoreComponent, candidate_canon: set[str]
    ) -> SkillGap:
        node = self.graph.resolve_alias(skill)
        adjacency: list[str] = []
        if node is not None:
            for nb in self.graph.neighbors(node.id, direction="both"):
                if nb.node.id in candidate_canon:
                    adjacency.append(nb.node.name)

        if adjacency:
            difficulty = "low"
        elif node is not None and node.type in _HARD_TYPES:
            difficulty = "high"
        else:
            difficulty = "medium"

        total = len(comp.matched_skills) + len(comp.missing_skills)
        expected_impact = round(comp.weight * (1 / total), 4) if total else 0.0

        return SkillGap(
            skill=skill,
            importance=importance,
            learning_difficulty=difficulty,
            estimated_learning_effort=_EFFORT_BY_DIFFICULTY[difficulty],
            expected_impact=expected_impact,
            adjacency_evidence=sorted(set(adjacency)),
        )

    @staticmethod
    def _summary(
        decision: DecisionProfile, job_title: str | None, candidate_name: str | None
    ) -> str:
        who = candidate_name or "The candidate"
        role = job_title or "the role"
        parts = [
            f"{who} is rated '{decision.recommendation.value}' for {role} with an overall "
            f"match of {decision.overall_match_score:.0%} "
            f"(confidence {decision.overall_confidence:.0%})."
        ]
        if decision.strengths:
            parts.append("Top strengths: " + ", ".join(decision.strengths[:3]) + ".")
        if decision.gaps:
            parts.append("Key gaps: " + ", ".join(decision.gaps[:3]) + ".")
        return " ".join(parts)

    async def _rewrite(self, explanation: ExplanationProfile) -> None:
        payload = {
            "executive_summary": explanation.executive_summary,
            "strengths": [s.description for s in explanation.strengths],
            "weaknesses": [w.description for w in explanation.weaknesses],
        }
        prompt = self.prompts.get(
            self.prompt_key, self.prompt_version, content=json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = await self.llm.generate_json(
                prompt, system=_REWRITE_SYSTEM, temperature=0.0, required_keys=["executive_summary"]
            )
        except Exception:
            return
        data = response.json_data or {}
        summary = data.get("executive_summary")
        if isinstance(summary, str) and summary.strip():
            explanation.executive_summary = summary
        new_strengths = data.get("strengths")
        if isinstance(new_strengths, list) and len(new_strengths) == len(explanation.strengths):
            for strength, text in zip(explanation.strengths, new_strengths, strict=False):
                if isinstance(text, str) and text.strip():
                    strength.description = text
        new_weak = data.get("weaknesses")
        if isinstance(new_weak, list) and len(new_weak) == len(explanation.weaknesses):
            for weakness, text in zip(explanation.weaknesses, new_weak, strict=False):
                if isinstance(text, str) and text.strip():
                    weakness.description = text
        explanation.llm_rewritten = True
        explanation.provider = response.provider
        explanation.model = response.model

    async def _rewrite_comparison(self, comparison: ComparisonProfile) -> None:
        payload = {"reasoning": comparison.reasoning}
        prompt = self.prompts.get(
            self.prompt_key, self.prompt_version, content=json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = await self.llm.generate_json(
                prompt, system=_REWRITE_SYSTEM, temperature=0.0, required_keys=["reasoning"]
            )
        except Exception:
            return
        data = response.json_data or {}
        reasoning = data.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            comparison.reasoning = reasoning
        comparison.llm_rewritten = True
        comparison.provider = response.provider
        comparison.model = response.model
