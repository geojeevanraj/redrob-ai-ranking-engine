"""Decision Intelligence Engine.

Compares one candidate (profile + hidden skills + DNA) against one job and
produces a deterministic, evidence-backed `DecisionProfile`. Scores are computed
by configurable, role-aware weighted algorithms — never by the LLM. The LLM may
only verify consistency and write a concise explanation (strengths / gaps).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.candidates.schema import CandidateProfile
from app.decision.model import DecisionProfile, Recommendation, ScoreComponent
from app.dna.model import CandidateDNA
from app.hidden_skills.model import HiddenSkillProfile
from app.jobs.schema import JobProfile
from app.knowledge import KnowledgeGraph, RelationshipType

_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_WEIGHTS = _DATA_DIR / "weights.json"

_SEMANTIC_RELS = {
    RelationshipType.RELATED_TO,
    RelationshipType.SIMILAR_TO,
    RelationshipType.PART_OF,
    RelationshipType.DEPENDENT_ON,
    RelationshipType.COMPLEMENTS,
    RelationshipType.REQUIRES,
}

# (key, display name) for every component.
COMPONENTS: list[tuple[str, str]] = [
    ("required_skill_match", "Required Skill Match"),
    ("preferred_skill_match", "Preferred Skill Match"),
    ("skill_coverage", "Skill Coverage Score"),
    ("technology_stack_match", "Technology Stack Match"),
    ("experience_alignment", "Experience Alignment"),
    ("project_relevance", "Project Relevance"),
    ("hidden_skill_contribution", "Hidden Skill Contribution"),
    ("dna_compatibility", "DNA Compatibility"),
    ("education_alignment", "Education Alignment"),
    ("career_progression", "Career Progression"),
    ("knowledge_graph_semantic_match", "Knowledge Graph Semantic Match"),
    # Optional behavioral signal (Sprint 9.1). Only contributes when a
    # behavioral profile is supplied to `compute()`; otherwise the component is
    # absent and existing decisions are byte-for-byte unchanged.
    ("behavioral_match", "Behavioral Match"),
]

_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_SENIORITY_RE = re.compile(
    r"\b(senior|lead|principal|staff|head|manager|director)\b", re.IGNORECASE
)


_VERIFY_SYSTEM = (
    "You verify and explain a deterministically-computed hiring decision. You "
    "must NOT change any score or the recommendation. Judge whether the scores "
    "are consistent with the evidence, then write a concise explanation and list "
    "notable strengths and major gaps grounded ONLY in the provided evidence. "
    "Respond with a single JSON object."
)


@dataclass
class DecisionConfig:
    profiles: dict[str, dict[str, float]]
    thresholds: dict[str, float]
    role_keywords: dict[str, str]
    semantic_partial_credit: float = 0.5


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


class BehavioralMatchLike(Protocol):
    """Structural contract for the optional behavioral signal.

    Implemented by `app.ranking.schemas.BehavioralProfile`. Declared as a
    Protocol so the Decision Engine stays decoupled from the ranking package
    (no import, no circular dependency).
    """

    overall_score: float
    confidence: float
    summary: str

    @property
    def top_signals(self) -> list[str]: ...


def load_decision_config(path: str | Path = _DEFAULT_WEIGHTS) -> DecisionConfig:
    """Load weighting profiles + thresholds from an external JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return DecisionConfig(
        profiles=data["profiles"],
        thresholds=data.get("thresholds", {"strong_hire": 0.8, "hire": 0.65, "consider": 0.45}),
        role_keywords=data.get("role_keywords", {}),
        semantic_partial_credit=float(data.get("semantic_partial_credit", 0.5)),
    )


@dataclass
class _MatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    total: int = 0


class DecisionIntelligenceEngine:
    """Deterministic candidate-vs-job scorer + LLM verifier."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        config: DecisionConfig,
        prompt_key: str = "decision/verify",
        prompt_version: int | str = "latest",
    ) -> None:
        self.graph = graph
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.config = config
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version

    # ── Deterministic evaluation (no LLM) ───────────────────
    def compute(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        *,
        hidden: HiddenSkillProfile | None = None,
        dna: CandidateDNA | None = None,
        behavioral: BehavioralMatchLike | None = None,
        weighting_profile: str | None = None,
    ) -> DecisionProfile:
        profile_name = self._select_profile(job, weighting_profile)
        weights = self.config.profiles[profile_name]

        explicit = self._canonical_set(self._explicit_terms(candidate))
        hidden_set = self._canonical_set(
            [s.inferred_skill for s in hidden.skills] if hidden else []
        )
        candidate_all = explicit | hidden_set

        required = self._score_skills(job.required_skills, candidate_all)
        preferred = self._score_skills(job.preferred_skills, candidate_all)
        stack_targets = job.technology_stack or job.technical_stack.all_technologies()
        stack = self._score_skills(stack_targets, candidate_all)
        kg = self._score_skills(
            self._dedupe([*job.required_skills, *job.preferred_skills, *stack_targets]),
            candidate_all,
        )

        components: list[ScoreComponent] = []
        components.append(self._skill_component("required_skill_match", required))
        components.append(self._skill_component("preferred_skill_match", preferred))
        components.append(self._coverage_component(required, preferred))
        components.append(self._skill_component("technology_stack_match", stack))
        components.append(self._experience_component(candidate, job))
        components.append(self._project_component(candidate, job, stack_targets))
        components.append(self._hidden_component(job, explicit, hidden_set, hidden, stack_targets))
        components.append(self._dna_component(dna, profile_name, job))
        components.append(self._education_component(candidate, job))
        components.append(self._career_component(candidate))
        components.append(self._kg_component("knowledge_graph_semantic_match", kg))

        if behavioral is not None:
            components.append(self._behavioral_component(behavioral))

        total_w = sum(weights.get(c.key, 0.0) for c in components) or 1.0
        overall = 0.0
        overall_conf = 0.0
        for c in components:
            c.weight = round(weights.get(c.key, 0.0) / total_w, 4)
            c.contribution = round(c.weight * c.score, 4)
            overall += c.contribution
            overall_conf += c.weight * c.confidence

        overall = round(overall, 4)
        recommendation = self._recommend(overall)
        strengths = [c.name for c in components if c.score >= 0.75]
        gaps = [c.name for c in components if c.score < 0.4]

        return DecisionProfile(
            overall_match_score=overall,
            overall_confidence=round(overall_conf, 4),
            recommendation=recommendation,
            weighting_profile=profile_name,
            components=components,
            strengths=strengths,
            gaps=gaps,
            reasoning_summary=(
                f"Overall match {overall:.2f} ({recommendation.value}) using the "
                f"'{profile_name}' weighting profile."
            ),
            timestamp=datetime.now(UTC),
            thresholds=dict(self.config.thresholds),
        )

    # ── Full evaluation (compute + LLM verify/summarize) ────
    async def generate(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        *,
        hidden: HiddenSkillProfile | None = None,
        dna: CandidateDNA | None = None,
        behavioral: BehavioralMatchLike | None = None,
        weighting_profile: str | None = None,
    ) -> DecisionProfile:
        decision = self.compute(
            candidate,
            job,
            hidden=hidden,
            dna=dna,
            behavioral=behavioral,
            weighting_profile=weighting_profile,
        )
        verified, summary, strengths, gaps, provider, model = await self._verify(decision)
        decision.llm_verified = verified
        if summary:
            decision.reasoning_summary = summary
        if strengths:
            decision.strengths = strengths
        if gaps:
            decision.gaps = gaps
        decision.provider = provider
        decision.model = model
        return decision

    # ── Profile selection ───────────────────────────────────
    def _select_profile(self, job: JobProfile, explicit: str | None) -> str:
        if explicit and explicit in self.config.profiles:
            return explicit
        title = (job.job_metadata.job_title or "").lower()
        for keyword, profile_id in self.config.role_keywords.items():
            if keyword in title and profile_id in self.config.profiles:
                return profile_id
        return "default"

    # ── Skill matching ──────────────────────────────────────
    def _explicit_terms(self, candidate: CandidateProfile) -> list[str]:
        terms = [*candidate.skills.all_skills(), *candidate.technology_stack]
        for exp in candidate.experience:
            terms.extend(exp.technologies)
        for proj in candidate.projects:
            terms.extend(proj.technologies)
        return terms

    def _canonical(self, term: str) -> str:
        node = self.graph.resolve_alias(term)
        return node.id if node is not None else term.strip().lower()

    def _canonical_set(self, terms: list[str]) -> set[str]:
        return {self._canonical(t) for t in terms if t and t.strip()}

    @staticmethod
    def _dedupe(terms: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for t in terms:
            key = t.strip().lower()
            if key and key not in seen:
                seen[key] = t.strip()
        return list(seen.values())

    def _match_target(self, target: str, candidate_all: set[str]) -> tuple[str, str | None]:
        canon = self._canonical(target)
        if canon in candidate_all:
            return "exact", None
        if self.graph.get_node(canon) is not None:
            for nb in self.graph.neighbors(canon, direction="both"):
                if nb.node.id in candidate_all and nb.edge.relationship in _SEMANTIC_RELS:
                    return "semantic", f"{canon} {nb.edge.relationship.value} {nb.node.id}"
        return "missing", None

    def _score_skills(self, targets: list[str], candidate_all: set[str]) -> _MatchResult:
        targets = self._dedupe(targets)
        if not targets:
            return _MatchResult(score=1.0, total=0)
        exact = 0
        semantic = 0
        matched: list[str] = []
        missing: list[str] = []
        rels: list[str] = []
        for t in targets:
            status, rel = self._match_target(t, candidate_all)
            if status == "exact":
                exact += 1
                matched.append(t)
            elif status == "semantic":
                semantic += 1
                matched.append(t)
                if rel:
                    rels.append(rel)
            else:
                missing.append(t)
        score = (exact + self.config.semantic_partial_credit * semantic) / len(targets)
        return _MatchResult(
            score=round(score, 3),
            matched=sorted(matched),
            missing=sorted(missing),
            relationships=sorted(rels),
            total=len(targets),
        )

    @staticmethod
    def _skill_confidence(total: int) -> float:
        if total == 0:
            return 0.3
        return round(min(1.0, 0.4 + total * 0.12), 3)

    def _skill_component(self, key: str, result: _MatchResult) -> ScoreComponent:
        name = dict(COMPONENTS)[key]
        return ScoreComponent(
            key=key,
            name=name,
            score=result.score,
            confidence=self._skill_confidence(result.total),
            matched_skills=result.matched,
            missing_skills=result.missing,
            supporting_evidence=[f"matched: {m}" for m in result.matched],
            missing_evidence=[f"missing: {m}" for m in result.missing],
            graph_relationships_used=result.relationships,
            reasoning_summary=(
                f"{len(result.matched)}/{result.total} target skills matched."
                if result.total
                else "No target skills specified; treated as satisfied."
            ),
        )

    def _kg_component(self, key: str, result: _MatchResult) -> ScoreComponent:
        comp = self._skill_component(key, result)
        comp.reasoning_summary = (
            f"Semantic coverage of {result.total} job skills via the knowledge "
            f"graph ({len(result.relationships)} graph relationships used)."
        )
        return comp

    def _coverage_component(
        self, required: _MatchResult, preferred: _MatchResult
    ) -> ScoreComponent:
        score = round(0.7 * required.score + 0.3 * preferred.score, 3)
        return ScoreComponent(
            key="skill_coverage",
            name="Skill Coverage Score",
            score=score,
            confidence=self._skill_confidence(required.total + preferred.total),
            matched_skills=sorted(set(required.matched) | set(preferred.matched)),
            missing_skills=sorted(set(required.missing) | set(preferred.missing)),
            supporting_evidence=[
                f"required {required.score:.2f}",
                f"preferred {preferred.score:.2f}",
            ],
            reasoning_summary="Weighted blend of required (0.7) and preferred (0.3) matches.",
        )

    # ── Non-skill components ────────────────────────────────
    def _experience_component(self, candidate: CandidateProfile, job: JobProfile) -> ScoreComponent:
        candidate_years = self._candidate_years(candidate)
        min_years = job.experience.minimum_years
        evidence = [f"candidate ≈ {candidate_years:g} yrs"]
        missing: list[str] = []
        if min_years is None or min_years <= 0:
            score = 1.0
            confidence = 0.3
            evidence.append("job specifies no minimum experience")
        else:
            score = round(min(1.0, candidate_years / min_years), 3)
            confidence = 0.7
            evidence.append(f"job requires ≥ {min_years:g} yrs")
            if candidate_years < min_years:
                missing.append(f"{min_years - candidate_years:g} more years")
        return ScoreComponent(
            key="experience_alignment",
            name="Experience Alignment",
            score=score,
            confidence=confidence,
            supporting_evidence=evidence,
            missing_evidence=missing,
            reasoning_summary=(
                f"Estimated {candidate_years:g} years vs required {min_years or 0:g}."
            ),
        )

    def _candidate_years(self, candidate: CandidateProfile) -> float:
        total = 0.0
        parsed_any = False
        for exp in candidate.experience:
            years = self._parse_years(exp.duration) or self._parse_span(
                exp.start_date, exp.end_date
            )
            if years:
                total += years
                parsed_any = True
        if not parsed_any:
            return float(len(candidate.experience))  # proxy: one year per role
        return round(total, 1)

    @staticmethod
    def _parse_years(text: str | None) -> float | None:
        if not text:
            return None
        m = _YEARS_RE.search(text)
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_span(start: str | None, end: str | None) -> float | None:
        if not start:
            return None
        start_m = _YEAR_RE.search(start)
        if not start_m:
            return None
        start_year = int(start_m.group(0))
        end_m = _YEAR_RE.search(end or "")
        end_year = int(end_m.group(0)) if end_m else datetime.now(UTC).year
        diff = end_year - start_year
        return float(diff) if diff > 0 else None

    def _project_component(
        self, candidate: CandidateProfile, job: JobProfile, stack_targets: list[str]
    ) -> ScoreComponent:
        job_set = self._canonical_set(stack_targets)
        matched_projects: list[str] = []
        covered: set[str] = set()
        for proj in candidate.projects:
            proj_canon = self._canonical_set(proj.technologies)
            overlap = proj_canon & job_set
            if overlap:
                matched_projects.append(proj.title or "Untitled project")
                covered |= overlap
        denom = max(1, len(job_set))
        score = (
            round(min(1.0, len(covered) / denom), 3)
            if job_set
            else (0.5 if candidate.projects else 0.0)
        )
        return ScoreComponent(
            key="project_relevance",
            name="Project Relevance",
            score=score,
            confidence=(
                round(min(1.0, len(candidate.projects) / 2), 3) if candidate.projects else 0.2
            ),
            matched_skills=sorted(covered),
            supporting_evidence=[f"relevant project: {p}" for p in matched_projects],
            reasoning_summary=(
                f"{len(matched_projects)} project(s) cover {len(covered)} job technologies."
            ),
        )

    def _hidden_component(
        self,
        job: JobProfile,
        explicit: set[str],
        hidden_set: set[str],
        hidden: HiddenSkillProfile | None,
        stack_targets: list[str],
    ) -> ScoreComponent:
        job_targets = self._canonical_set(
            [*job.required_skills, *job.preferred_skills, *stack_targets]
        )
        added = sorted(t for t in job_targets if t not in explicit and t in hidden_set)
        denom = max(1, len(job_targets))
        score = round(len(added) / denom, 3)
        return ScoreComponent(
            key="hidden_skill_contribution",
            name="Hidden Skill Contribution",
            score=score,
            confidence=0.9 if hidden else 0.2,
            matched_skills=added,
            supporting_evidence=[f"hidden skill covers: {a}" for a in added],
            reasoning_summary=(
                f"{len(added)} job requirement(s) covered by inferred (hidden) skills."
                if hidden
                else "No hidden-skill profile available."
            ),
        )

    def _dna_component(
        self, dna: CandidateDNA | None, profile_name: str, job: JobProfile
    ) -> ScoreComponent:
        desired = profile_name if profile_name != "default" else None
        if dna is None:
            return ScoreComponent(
                key="dna_compatibility",
                name="DNA Compatibility",
                score=0.5,
                confidence=0.2,
                missing_evidence=["no candidate DNA available"],
                reasoning_summary="Neutral — candidate DNA not available.",
            )
        if desired is None:
            top = dna.archetypes[0].score if dna.archetypes else 0.5
            return ScoreComponent(
                key="dna_compatibility",
                name="DNA Compatibility",
                score=round(top, 3),
                confidence=0.4,
                supporting_evidence=[f"top archetype score {top:.2f}"],
                reasoning_summary="No role-specific archetype; used top archetype score.",
            )
        match = next((a for a in dna.archetypes if a.archetype_id == desired), None)
        score = round(match.score, 3) if match else 0.0
        return ScoreComponent(
            key="dna_compatibility",
            name="DNA Compatibility",
            score=score,
            confidence=0.9 if match else 0.5,
            supporting_evidence=[f"{desired} archetype score {score:.2f}"] if match else [],
            missing_evidence=[] if match else [f"no '{desired}' archetype affinity"],
            reasoning_summary=f"Candidate '{desired}' DNA affinity = {score:.2f}.",
        )

    def _education_component(self, candidate: CandidateProfile, job: JobProfile) -> ScoreComponent:
        required = job.education.required
        has_education = bool(candidate.education)
        if not required:
            return ScoreComponent(
                key="education_alignment",
                name="Education Alignment",
                score=1.0,
                confidence=0.3,
                supporting_evidence=["job specifies no required education"],
                reasoning_summary="No education requirement; treated as satisfied.",
            )
        degrees = " ".join(
            f"{e.degree or ''} {e.field_of_study or ''}".lower() for e in candidate.education
        )
        matched = [r for r in required if any(tok in degrees for tok in r.lower().split())]
        if matched:
            score = 1.0
        elif has_education:
            score = 0.4
        else:
            score = 0.0
        return ScoreComponent(
            key="education_alignment",
            name="Education Alignment",
            score=score,
            confidence=0.6,
            supporting_evidence=[f"matched requirement: {m}" for m in matched],
            missing_evidence=[f"required: {r}" for r in required if r not in matched],
            reasoning_summary=f"{len(matched)}/{len(required)} education requirements met.",
        )

    def _career_component(self, candidate: CandidateProfile) -> ScoreComponent:
        roles = candidate.experience
        seniority_hits = sum(1 for e in roles if _SENIORITY_RE.search(f"{e.role or ''}"))
        breadth = min(1.0, len(roles) / 3)
        seniority = min(1.0, seniority_hits / 2)
        score = round(0.6 * breadth + 0.4 * seniority, 3)
        return ScoreComponent(
            key="career_progression",
            name="Career Progression",
            score=score,
            confidence=0.3,
            supporting_evidence=[
                f"{len(roles)} role(s)",
                f"{seniority_hits} seniority signal(s)",
            ],
            reasoning_summary="Deterministic proxy from role count and seniority signals.",
        )

    def _behavioral_component(self, behavioral: BehavioralMatchLike) -> ScoreComponent:
        """Wrap the deterministic behavioral score as a decision sub-component.

        The score is consumed as-is from the Behavioral Intelligence Engine —
        the Decision Engine performs no behavioral reasoning of its own.
        """
        score = round(max(0.0, min(1.0, behavioral.overall_score)), 3)
        return ScoreComponent(
            key="behavioral_match",
            name="Behavioral Match",
            score=score,
            confidence=round(max(0.0, min(1.0, behavioral.confidence)), 3),
            supporting_evidence=list(behavioral.top_signals),
            reasoning_summary=behavioral.summary
            or f"Behavioral match {score:.2f} from engagement signals.",
        )

    # ── Recommendation ──────────────────────────────────────
    def _recommend(self, overall: float) -> Recommendation:
        t = self.config.thresholds
        if overall >= t.get("strong_hire", 0.8):
            return Recommendation.STRONG_HIRE
        if overall >= t.get("hire", 0.65):
            return Recommendation.HIRE
        if overall >= t.get("consider", 0.45):
            return Recommendation.CONSIDER
        return Recommendation.REJECT

    # ── LLM verification ────────────────────────────────────
    async def _verify(
        self, decision: DecisionProfile
    ) -> tuple[bool, str | None, list[str], list[str], str | None, str | None]:
        payload = {
            "overall_match_score": decision.overall_match_score,
            "recommendation": decision.recommendation.value,
            "components": [
                {
                    "name": c.name,
                    "score": c.score,
                    "matched_skills": c.matched_skills,
                    "missing_skills": c.missing_skills,
                }
                for c in decision.components
            ],
        }
        prompt = self.prompts.get(
            self.prompt_key,
            self.prompt_version,
            decision=json.dumps(payload, ensure_ascii=False),
        )
        response = await self.llm.generate_json(
            prompt,
            system=_VERIFY_SYSTEM,
            temperature=0.0,
            required_keys=["consistent"],
        )
        data = response.json_data or {}
        verified = bool(data.get("consistent", False))
        summary = data.get("summary")
        strengths = data.get("strengths") if isinstance(data.get("strengths"), list) else None
        gaps = data.get("gaps") if isinstance(data.get("gaps"), list) else None
        return (
            verified,
            str(summary) if summary else None,
            [str(s) for s in strengths] if strengths else [],
            [str(g) for g in gaps] if gaps else [],
            response.provider,
            response.model,
        )
