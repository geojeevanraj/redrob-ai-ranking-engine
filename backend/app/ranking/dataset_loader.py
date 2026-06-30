"""Streaming JSONL loader for the official Redrob candidate dataset.

Designed for the hackathon constraints: must handle 100,000 candidates on CPU,
under 16 GB, without ever materializing the whole file in memory. The loader is
a generator that yields one candidate at a time in deterministic file order.

Each Redrob row is mapped onto the existing canonical `CandidateProfile` (the
input contract for every downstream engine) — NO schema duplication and NO
Candidate Intelligence extraction. Behavioral `redrob_signals` are returned
alongside, since they are not part of a resume.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from app.candidates.schema import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    PersonalInfo,
    Skills,
)
from app.ranking.schemas import RedrobCandidate, RedrobSignals


class DatasetError(Exception):
    """Raised when the dataset cannot be read."""


def stream_candidates(path: str | Path) -> Iterator[RedrobCandidate]:
    """Yield validated `RedrobCandidate` rows from a JSONL file, one at a time.

    Blank lines are skipped. Malformed JSON lines are skipped (they cannot be
    trusted). The file handle streams line-by-line, so memory stays O(1) in the
    row count — safe for the official 100,000-candidate dataset.
    """
    p = Path(path)
    if not p.exists():
        raise DatasetError(f"Dataset not found: {p}")
    with p.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            yield RedrobCandidate.model_validate(raw)


def stream_profiles(
    path: str | Path,
) -> Iterator[tuple[str, CandidateProfile, RedrobSignals]]:
    """Yield ``(candidate_id, CandidateProfile, RedrobSignals)`` deterministically."""
    for redrob in stream_candidates(path):
        yield redrob.candidate_id, to_candidate_profile(redrob), redrob.redrob_signals


def to_candidate_profile(redrob: RedrobCandidate) -> CandidateProfile:
    """Map a structured Redrob candidate onto the canonical `CandidateProfile`.

    The mapping is purely structural — it copies already-structured fields into
    their canonical home. Skill matching downstream is graph-alias based and
    category-agnostic, so flat Redrob skills are placed in `skills.tools` and
    mirrored into `technology_stack` (deduped, order-preserving).
    """
    p = redrob.profile

    personal = PersonalInfo(
        full_name=p.full_name,
        email=p.email,
        phone=p.phone,
        location=p.location,
        linkedin=p.linkedin,
        github=p.github,
        portfolio=p.portfolio,
    )

    experience = [
        ExperienceEntry(
            company=c.company,
            role=c.role or c.title,
            start_date=c.start_date,
            end_date=c.end_date,
            duration=_duration_text(c.duration, c.duration_months),
            responsibilities=list(c.responsibilities),
            technologies=list(c.technologies),
            business_impact=c.description,
        )
        for c in redrob.career_history
    ]

    education = [
        EducationEntry(
            institution=e.institution,
            degree=e.degree,
            field_of_study=e.field_of_study,
            start_date=e.start_date,
            end_date=e.end_date,
            grade=e.grade,
        )
        for e in redrob.education
    ]

    stack = _dedupe(redrob.skills)

    return CandidateProfile(
        personal_info=personal,
        professional_summary=p.summary or p.headline,
        education=education,
        experience=experience,
        skills=Skills(tools=list(stack)),
        certifications=list(redrob.certifications),
        languages_known=list(redrob.languages),
        technology_stack=stack,
    )


def _dedupe(terms: list[str]) -> list[str]:
    """Case-insensitive dedupe, order-preserving (matches engine convention)."""
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        key = t.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(t.strip())
    return out


def _duration_text(duration: str | None, duration_months: int | None) -> str | None:
    """Prefer the official integer ``duration_months`` as a years string.

    The Decision Engine parses experience from a ``"<n> years"`` phrase (falling
    back to start/end dates). Converting the official month count gives the most
    accurate per-role tenure without changing any engine logic.
    """
    if duration_months is not None and duration_months > 0:
        return f"{duration_months / 12:.1f} years"
    return duration
