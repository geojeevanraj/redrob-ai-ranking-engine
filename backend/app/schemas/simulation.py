"""Hiring Simulator schemas.

The simulator reuses the existing deterministic Decision Intelligence Engine and
Explainability Engine. It only changes *inputs* (a modified job + bounded weight
overrides) and recomputes — it never persists or mutates stored evaluations, and
it does not change any engine logic.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.explainability.model import ExplanationProfile


class SimulationRequest(BaseModel):
    """Editable hiring criteria for a what-if scenario."""

    job_id: uuid.UUID
    candidate_ids: list[uuid.UUID] | None = None  # None => all candidates

    # Role weighting profile (e.g. "backend_engineer", "ai_engineer").
    role_profile: str | None = None

    # Skill edits.
    move_to_required: list[str] = Field(default_factory=list)
    move_to_preferred: list[str] = Field(default_factory=list)
    add_required: list[str] = Field(default_factory=list)
    add_preferred: list[str] = Field(default_factory=list)
    remove_skills: list[str] = Field(default_factory=list)

    # Requirement edits.
    min_experience: float | None = None
    education_required: list[str] | None = None

    # Bounded component-weight overrides (raw weights; the engine normalizes).
    weight_overrides: dict[str, float] = Field(default_factory=dict)


class ComponentDelta(BaseModel):
    key: str
    name: str
    baseline: float
    new: float
    delta: float


class CandidateSimResult(BaseModel):
    candidate_id: str
    candidate_name: str | None
    baseline_score: float
    new_score: float
    delta: float
    baseline_rank: int
    new_rank: int
    rank_delta: int  # positive = moved up
    baseline_recommendation: str
    new_recommendation: str
    component_deltas: list[ComponentDelta]
    change_reasons: list[str]
    explanation: ExplanationProfile


class SimulationResult(BaseModel):
    weighting_profile: str
    applied_overrides: dict[str, object]
    results: list[CandidateSimResult]
