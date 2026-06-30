"""Candidate DNA data model.

`CandidateDNA` is an evidence-based professional *fingerprint*: a set of
archetype affinities computed deterministically from observable technical
evidence (skills, inferred skills, projects, experience, technologies, domains).

It must NEVER contain personality or psychological inference — every archetype
is traceable to concrete supporting evidence.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArchetypeScore(BaseModel):
    """One professional archetype with its score and supporting evidence."""

    model_config = ConfigDict(extra="ignore")

    archetype: str  # display name, e.g. "Backend Engineer"
    archetype_id: str  # stable id, e.g. "backend_engineer"
    score: float  # 0..1 (deterministic)
    confidence: float  # 0..1 (based on amount/diversity of evidence)
    evidence: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    supporting_hidden_skills: list[str] = Field(default_factory=list)
    supporting_projects: list[str] = Field(default_factory=list)
    supporting_experience: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    llm_verified: bool = False


class CandidateDNA(BaseModel):
    """A candidate's professional fingerprint across archetypes."""

    model_config = ConfigDict(extra="ignore")

    archetypes: list[ArchetypeScore] = Field(default_factory=list)
    top_archetypes: list[str] = Field(default_factory=list)
    emerging_archetypes: list[str] = Field(default_factory=list)
    weak_archetypes: list[str] = Field(default_factory=list)
    overall_engineering_focus: str = "Undetermined"
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)
