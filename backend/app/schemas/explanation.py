"""Explanation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.explainability.model import ComparisonProfile, ExplanationProfile
from app.models.explanation import ExplanationRecord


class GenerateRequest(BaseModel):
    decision_id: uuid.UUID


class CompareRequest(BaseModel):
    decision_id_a: uuid.UUID
    decision_id_b: uuid.UUID


class ExplanationRead(BaseModel):
    id: str
    decision_id: str
    recommendation: str | None
    llm_provider: str | None
    llm_model: str | None
    explanation: ExplanationProfile
    created_at: datetime


def to_read(record: ExplanationRecord) -> ExplanationRead:
    return ExplanationRead(
        id=str(record.id),
        decision_id=str(record.decision_id),
        recommendation=record.recommendation,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        explanation=ExplanationProfile.model_validate(record.explanation),
        created_at=record.created_at,
    )


class ComparisonResponse(BaseModel):
    comparison: ComparisonProfile
