"""Decision Intelligence data model.

`DecisionProfile` is a transparent, reproducible, evidence-backed hiring
recommendation comparing one candidate to one job. Every sub-score carries its
supporting + missing evidence, and the overall recommendation is fully
traceable. Scores are computed deterministically; the LLM may only verify and
summarize — never modify a score.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Recommendation(str, Enum):
    STRONG_HIRE = "Strong Hire"
    HIRE = "Hire"
    CONSIDER = "Consider"
    REJECT = "Reject"


class ScoreComponent(BaseModel):
    """One deterministic sub-score with its evidence."""

    model_config = ConfigDict(extra="ignore")

    key: str
    name: str
    score: float  # 0..1
    weight: float = 0.0  # normalized weight in the active profile
    contribution: float = 0.0  # weight * score
    confidence: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    graph_relationships_used: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class DecisionProfile(BaseModel):
    """A complete hiring recommendation for a (candidate, job) pair."""

    model_config = ConfigDict(extra="ignore")

    overall_match_score: float
    overall_confidence: float
    recommendation: Recommendation
    weighting_profile: str
    components: list[ScoreComponent] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    llm_verified: bool = False
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)
