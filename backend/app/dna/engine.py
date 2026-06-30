"""Candidate DNA Engine.

Produces an evidence-based professional fingerprint. Scoring is **fully
deterministic** — archetype affinities are computed from observable technical
evidence (explicit + inferred skills, project/experience technologies, domains)
using configurable weighted rules. The LLM may ONLY verify consistency and
write a concise summary; it can never change a score.

No personality or psychological inference is performed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.candidates.schema import CandidateProfile
from app.dna.model import ArchetypeScore, CandidateDNA
from app.hidden_skills.model import HiddenSkillProfile
from app.knowledge import KnowledgeGraph

_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_ARCHETYPES = _DATA_DIR / "archetypes.json"

_VERIFY_SYSTEM = (
    "You verify and summarize a deterministically-computed professional DNA "
    "profile. You must NOT change any score. Only judge whether each archetype "
    "is consistent with its listed evidence and write a one-sentence, "
    "evidence-grounded summary. Never infer personality or psychological traits. "
    "Respond with a single JSON object."
)


@dataclass
class ArchetypeRule:
    """A configurable weighted rule defining an archetype."""

    id: str
    name: str
    keywords: dict[str, float] = field(default_factory=dict)
    categories: dict[str, float] = field(default_factory=dict)
    saturation: float = 3.0


@dataclass
class DNAConfig:
    """Thresholds + archetype rules (data-driven, configurable)."""

    archetypes: list[ArchetypeRule]
    top_threshold: float = 0.6
    emerging_threshold: float = 0.3
    confidence_items: int = 5
    default_saturation: float = 3.0


@dataclass
class _Term:
    """A canonicalized candidate evidence term with provenance."""

    display: str
    category: str | None
    skills: set[str] = field(default_factory=set)
    hidden_skills: set[str] = field(default_factory=set)
    projects: set[str] = field(default_factory=set)
    experience: set[str] = field(default_factory=set)


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


def load_archetypes(path: str | Path = _DEFAULT_ARCHETYPES) -> list[ArchetypeRule]:
    """Load archetype rules from a JSON config file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules: list[ArchetypeRule] = []
    for item in data.get("archetypes", []):
        rules.append(
            ArchetypeRule(
                id=item["id"],
                name=item["name"],
                keywords={k.lower(): float(v) for k, v in item.get("keywords", {}).items()},
                categories={k: float(v) for k, v in item.get("categories", {}).items()},
                saturation=float(item.get("saturation", 3.0)),
            )
        )
    return rules


class CandidateDNAEngine:
    """Deterministic archetype scorer + LLM verifier/summarizer."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        llm_manager: LLMManagerLike,
        prompt_manager: PromptManagerLike,
        *,
        config: DNAConfig,
        prompt_key: str = "dna/verify",
        prompt_version: int | str = "latest",
    ) -> None:
        self.graph = graph
        self.llm = llm_manager
        self.prompts = prompt_manager
        self.config = config
        self.prompt_key = prompt_key
        self.prompt_version = prompt_version
        # Pre-canonicalize archetype keywords once.
        self._canonical_keywords: dict[str, dict[str, float]] = {}
        for rule in config.archetypes:
            self._canonical_keywords[rule.id] = {
                self._canonical(term): weight for term, weight in rule.keywords.items()
            }

    # ── Deterministic scoring (no LLM) ──────────────────────
    def compute(
        self, profile: CandidateProfile, hidden: HiddenSkillProfile | None = None
    ) -> CandidateDNA:
        terms = self._build_terms(profile, hidden)
        scored: list[ArchetypeScore] = []

        for rule in self.config.archetypes:
            result = self._score_archetype(rule, terms)
            if result is not None:
                scored.append(result)

        scored.sort(key=lambda a: (-a.score, a.archetype_id))

        top = [a.archetype for a in scored if a.score >= self.config.top_threshold]
        emerging = [
            a.archetype
            for a in scored
            if self.config.emerging_threshold <= a.score < self.config.top_threshold
        ]
        weak = [a.archetype for a in scored if 0 < a.score < self.config.emerging_threshold]
        focus = scored[0].archetype if scored else "Undetermined"

        return CandidateDNA(
            archetypes=scored,
            top_archetypes=top,
            emerging_archetypes=emerging,
            weak_archetypes=weak,
            overall_engineering_focus=focus,
            timestamp=datetime.now(UTC),
            thresholds={
                "top_threshold": self.config.top_threshold,
                "emerging_threshold": self.config.emerging_threshold,
                "confidence_items": float(self.config.confidence_items),
            },
        )

    # ── Full generation (compute + LLM verify/summarize) ────
    async def generate(
        self, profile: CandidateProfile, hidden: HiddenSkillProfile | None = None
    ) -> CandidateDNA:
        dna = self.compute(profile, hidden)
        if not dna.archetypes:
            return dna

        verifications, summaries, provider, model = await self._verify(dna)
        for arch in dna.archetypes:
            arch.llm_verified = bool(verifications.get(arch.archetype_id, False))
            summary = summaries.get(arch.archetype_id)
            if summary:
                arch.reasoning_summary = summary
        dna.provider = provider
        dna.model = model
        return dna

    # ── Internals ───────────────────────────────────────────
    def _canonical(self, term: str) -> str:
        node = self.graph.resolve_alias(term)
        return node.id if node is not None else term.strip().lower()

    def _build_terms(
        self, profile: CandidateProfile, hidden: HiddenSkillProfile | None
    ) -> dict[str, _Term]:
        terms: dict[str, _Term] = {}

        def add(
            raw: str,
            *,
            skill: str | None = None,
            hidden_name: str | None = None,
            project: str | None = None,
            experience: str | None = None,
        ) -> None:
            if not raw or not raw.strip():
                return
            node = self.graph.resolve_alias(raw)
            canon = node.id if node is not None else raw.strip().lower()
            display = node.name if node is not None else raw.strip()
            category = node.category if node is not None else None
            entry = terms.get(canon)
            if entry is None:
                entry = _Term(display=display, category=category)
                terms[canon] = entry
            if skill:
                entry.skills.add(skill)
            if hidden_name:
                entry.hidden_skills.add(hidden_name)
            if project:
                entry.projects.add(project)
            if experience:
                entry.experience.add(experience)

        for skill in profile.skills.all_skills():
            add(skill, skill=skill)
        for tech in profile.technology_stack:
            add(tech, skill=tech)
        for exp in profile.experience:
            label = f"{exp.role or '?'} @ {exp.company or '?'}"
            for tech in exp.technologies:
                add(tech, experience=label)
        for proj in profile.projects:
            title = proj.title or "Untitled project"
            for tech in proj.technologies:
                add(tech, project=title)
            if proj.domain:
                add(proj.domain, project=title)
        if hidden is not None:
            for hs in hidden.skills:
                add(hs.inferred_skill, hidden_name=hs.inferred_skill)

        return terms

    def _score_archetype(
        self, rule: ArchetypeRule, terms: dict[str, _Term]
    ) -> ArchetypeScore | None:
        matched_weight = 0.0
        matched_terms: set[str] = set()
        evidence: list[str] = []
        skills: set[str] = set()
        hidden_skills: set[str] = set()
        projects: set[str] = set()
        experience: set[str] = set()

        canonical_keywords = self._canonical_keywords[rule.id]

        # Keyword matches.
        for canon, weight in canonical_keywords.items():
            term = terms.get(canon)
            if term is not None:
                matched_weight += weight
                matched_terms.add(canon)
                evidence.append(f"{term.display} (+{weight:g})")
                skills |= term.skills
                hidden_skills |= term.hidden_skills
                projects |= term.projects
                experience |= term.experience

        # Category matches (counted once per category present).
        for category, weight in rule.categories.items():
            in_category = [c for c, t in terms.items() if t.category == category]
            if in_category:
                matched_weight += weight
                evidence.append(f"category:{category} (+{weight:g})")
                for c in in_category:
                    if c not in matched_terms:
                        term = terms[c]
                        skills |= term.skills
                        hidden_skills |= term.hidden_skills
                        projects |= term.projects
                        experience |= term.experience

        if matched_weight <= 0:
            return None

        saturation = rule.saturation or self.config.default_saturation
        score = round(min(1.0, matched_weight / saturation), 3)

        distinct_evidence = len(matched_terms) + sum(
            1 for cat in rule.categories if any(t.category == cat for t in terms.values())
        )
        confidence = round(min(1.0, distinct_evidence / self.config.confidence_items), 3)

        return ArchetypeScore(
            archetype=rule.name,
            archetype_id=rule.id,
            score=score,
            confidence=confidence,
            evidence=sorted(evidence),
            supporting_skills=sorted(skills),
            supporting_hidden_skills=sorted(hidden_skills),
            supporting_projects=sorted(projects),
            supporting_experience=sorted(experience),
            reasoning_summary=(
                f"Scored {score} from {len(matched_terms)} matching technologies/"
                f"categories for {rule.name}."
            ),
            llm_verified=False,
        )

    async def _verify(
        self, dna: CandidateDNA
    ) -> tuple[dict[str, bool], dict[str, str], str | None, str | None]:
        payload = [
            {
                "archetype_id": a.archetype_id,
                "archetype": a.archetype,
                "score": a.score,
                "evidence": a.evidence,
                "supporting_skills": a.supporting_skills,
            }
            for a in dna.archetypes
        ]
        prompt = self.prompts.get(
            self.prompt_key,
            self.prompt_version,
            archetypes=json.dumps(payload, ensure_ascii=False),
        )
        response = await self.llm.generate_json(
            prompt,
            system=_VERIFY_SYSTEM,
            temperature=0.0,
            required_keys=["archetypes"],
        )
        data = response.json_data or {}
        verifications: dict[str, bool] = {}
        summaries: dict[str, str] = {}
        for item in data.get("archetypes", []):
            if isinstance(item, dict) and "archetype_id" in item:
                aid = str(item["archetype_id"])
                verifications[aid] = bool(item.get("consistent", False))
                if item.get("reasoning"):
                    summaries[aid] = str(item["reasoning"])
        return verifications, summaries, response.provider, response.model
