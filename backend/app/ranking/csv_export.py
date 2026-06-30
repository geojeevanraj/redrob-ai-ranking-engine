"""Deterministic CSV export for the offline ranking engine.

Produces exactly the four official columns — ``candidate_id``, ``rank``,
``score``, ``reasoning`` — for the top-N candidates. Reasoning is constructed
DETERMINISTICALLY from existing evidence (matched skills, experience, behavioral
signals, gaps). The LLM / Gemini is NEVER used here, so there are no
hallucinations and the output is fully reproducible.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.decision.model import DecisionProfile
from app.ranking.schemas import BehavioralProfile

if TYPE_CHECKING:
    from app.ranking.schemas import RankedCandidate

_YEARS_EVIDENCE_RE = re.compile(r"≈\s*(\d+(?:\.\d+)?)")

# Components whose matched skills count as "strengths" for reasoning.
_STRENGTH_KEYS = ("required_skill_match", "technology_stack_match", "preferred_skill_match")


def collect_matched_skills(decision: DecisionProfile, *, limit: int = 8) -> list[str]:
    """Ordered, deduped matched skills across the key skill components."""
    seen: set[str] = set()
    out: list[str] = []
    for key in _STRENGTH_KEYS:
        comp = next((c for c in decision.components if c.key == key), None)
        if comp is None:
            continue
        for skill in comp.matched_skills:
            low = skill.lower()
            if low not in seen:
                seen.add(low)
                out.append(skill)
    return out[:limit]


def collect_missing_skills(decision: DecisionProfile, *, limit: int = 4) -> list[str]:
    """Ordered, deduped missing skills from the required-skill component first."""
    seen: set[str] = set()
    out: list[str] = []
    for key in ("required_skill_match", "technology_stack_match"):
        comp = next((c for c in decision.components if c.key == key), None)
        if comp is None:
            continue
        for skill in comp.missing_skills:
            low = skill.lower()
            if low not in seen:
                seen.add(low)
                out.append(skill)
    return out[:limit]


def estimate_years(decision: DecisionProfile) -> float | None:
    """Recover the candidate's estimated experience years from evidence text."""
    comp = next((c for c in decision.components if c.key == "experience_alignment"), None)
    if comp is None:
        return None
    for ev in comp.supporting_evidence:
        m = _YEARS_EVIDENCE_RE.search(ev)
        if m:
            return float(m.group(1))
    return None


def build_reasoning(
    decision: DecisionProfile,
    behavioral: BehavioralProfile,
    *,
    max_strength_skills: int = 4,
    min_experience_mention_years: float = 0.5,
    strong_behavioral_threshold: float = 0.70,
) -> str:
    """Construct a concise (max two sentences) deterministic rationale.

    Example shape:
        "7.2 years experience with Python, FastAPI, PostgreSQL and strong
        recruiter engagement. Missing Kubernetes, Go."
    """
    strengths = collect_matched_skills(decision, limit=max_strength_skills)
    years = estimate_years(decision)

    lead_parts: list[str] = []
    if years is not None and years >= min_experience_mention_years:
        lead_parts.append(f"{years:g} years experience")
    if strengths:
        connector = " with " if lead_parts else "Strong match on "
        lead_parts.append(f"{connector}{_join(strengths)}")
    elif not lead_parts:
        lead_parts.append(f"{decision.recommendation.value} candidate")

    behavioral_clause = ""
    if behavioral.overall_score >= strong_behavioral_threshold:
        behavioral_clause = " and strong recruiter engagement"

    sentence_one = f"{''.join(lead_parts)}{behavioral_clause}.".strip()
    sentence_one = sentence_one[0].upper() + sentence_one[1:] if sentence_one else sentence_one

    missing = collect_missing_skills(decision)
    sentence_two = f" Missing {_join(missing)}." if missing else ""

    return (sentence_one + sentence_two).strip()


def write_ranking_csv(rows: list[RankedCandidate], path: str | Path) -> Path:
    """Write the official 4-column CSV (candidate_id, rank, score, reasoning)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for row in rows:
            writer.writerow([row.candidate_id, row.rank, f"{row.score:.4f}", row.reasoning])
    return p


def _join(items: list[str]) -> str:
    """Human-friendly join: 'a, b and c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"
