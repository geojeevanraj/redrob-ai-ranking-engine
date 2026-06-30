"""Explainability data model.

`ExplanationProfile` turns a `DecisionProfile` into a transparent, evidence-backed
narrative. Every statement maps to evidence carried by the decision's score
components — nothing is invented. `ComparisonProfile` compares two decisions.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Strength(BaseModel):
    description: str
    evidence: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    supporting_projects: list[str] = Field(default_factory=list)
    supporting_experience: list[str] = Field(default_factory=list)


class Weakness(BaseModel):
    description: str
    missing_evidence: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    missing_experience: list[str] = Field(default_factory=list)


class SkillGap(BaseModel):
    skill: str
    importance: str  # "required" | "preferred"
    learning_difficulty: str  # "low" | "medium" | "high"
    estimated_learning_effort: str  # e.g. "~6 weeks"
    expected_impact: float  # increase in overall match score if covered
    adjacency_evidence: list[str] = Field(default_factory=list)  # related skills held


class ScoreExplanation(BaseModel):
    component_key: str
    name: str
    score: float
    why: str
    evidence: list[str] = Field(default_factory=list)


class ExplanationProfile(BaseModel):
    """A full, evidence-backed explanation of a hiring decision."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str | None = None
    executive_summary: str = ""
    recommendation: str = ""
    overall_match_score: float = 0.0
    overall_confidence: float = 0.0
    strengths: list[Strength] = Field(default_factory=list)
    weaknesses: list[Weakness] = Field(default_factory=list)
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    score_breakdown: list[ScoreExplanation] = Field(default_factory=list)
    llm_rewritten: bool = False
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None


class ComponentComparison(BaseModel):
    key: str
    name: str
    score_a: float
    score_b: float
    leader: str  # "A" | "B" | "Tie"


class ComparisonProfile(BaseModel):
    """A transparent comparison of two hiring decisions."""

    model_config = ConfigDict(extra="ignore")

    decision_a_id: str | None = None
    decision_b_id: str | None = None
    overall_a: float = 0.0
    overall_b: float = 0.0
    winner: str = "Tie"  # "A" | "B" | "Tie"
    advantages_a: list[str] = Field(default_factory=list)
    advantages_b: list[str] = Field(default_factory=list)
    disadvantages_a: list[str] = Field(default_factory=list)
    disadvantages_b: list[str] = Field(default_factory=list)
    component_comparison: list[ComponentComparison] = Field(default_factory=list)
    reasoning: str = ""
    llm_rewritten: bool = False
    provider: str | None = None
    model: str | None = None
    timestamp: datetime | None = None
