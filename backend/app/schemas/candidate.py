"""Candidate API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.candidates.schema import CandidateProfile
from app.models.candidate import CandidateProfileRecord


class CandidateSummary(BaseModel):
    """Lightweight view for listings."""

    id: str
    document_id: str
    full_name: str | None
    email: str | None
    extraction_confidence: float
    created_at: datetime


class CandidateProfileRead(CandidateSummary):
    """Full view including the structured profile and LLM provenance."""

    llm_provider: str | None
    llm_model: str | None
    profile: CandidateProfile


def to_summary(record: CandidateProfileRecord) -> CandidateSummary:
    return CandidateSummary(
        id=str(record.id),
        document_id=str(record.document_id),
        full_name=record.full_name,
        email=record.email,
        extraction_confidence=record.extraction_confidence,
        created_at=record.created_at,
    )


def to_read(record: CandidateProfileRecord) -> CandidateProfileRead:
    return CandidateProfileRead(
        id=str(record.id),
        document_id=str(record.document_id),
        full_name=record.full_name,
        email=record.email,
        extraction_confidence=record.extraction_confidence,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        profile=CandidateProfile.model_validate(record.profile),
        created_at=record.created_at,
    )
