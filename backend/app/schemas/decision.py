"""Decision API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.decision.model import DecisionProfile
from app.models.decision import DecisionRecord


class EvaluateRequest(BaseModel):
    """Request body for a candidate-vs-job evaluation."""

    candidate_id: uuid.UUID
    job_id: uuid.UUID
    weighting_profile: str | None = None


class DecisionSummary(BaseModel):
    """Lightweight view for listings."""

    id: str
    candidate_id: str
    job_id: str
    overall_match_score: float
    recommendation: str
    weighting_profile: str
    created_at: datetime


class DecisionRead(DecisionSummary):
    """Full view including the decision profile and LLM provenance."""

    llm_provider: str | None
    llm_model: str | None
    decision: DecisionProfile


def to_summary(record: DecisionRecord) -> DecisionSummary:
    return DecisionSummary(
        id=str(record.id),
        candidate_id=str(record.candidate_id),
        job_id=str(record.job_id),
        overall_match_score=record.overall_match_score,
        recommendation=record.recommendation,
        weighting_profile=record.weighting_profile,
        created_at=record.created_at,
    )


def to_read(record: DecisionRecord) -> DecisionRead:
    return DecisionRead(
        id=str(record.id),
        candidate_id=str(record.candidate_id),
        job_id=str(record.job_id),
        overall_match_score=record.overall_match_score,
        recommendation=record.recommendation,
        weighting_profile=record.weighting_profile,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        decision=DecisionProfile.model_validate(record.decision),
        created_at=record.created_at,
    )
