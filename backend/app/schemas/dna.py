"""Candidate DNA API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.dna.model import CandidateDNA
from app.models.dna import CandidateDNARecord


class CandidateDNARead(BaseModel):
    """Full view of a persisted candidate DNA profile."""

    id: str
    candidate_id: str
    overall_focus: str | None
    top_archetype: str | None
    llm_provider: str | None
    llm_model: str | None
    dna: CandidateDNA
    created_at: datetime


def to_read(record: CandidateDNARecord) -> CandidateDNARead:
    return CandidateDNARead(
        id=str(record.id),
        candidate_id=str(record.candidate_id),
        overall_focus=record.overall_focus,
        top_archetype=record.top_archetype,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        dna=CandidateDNA.model_validate(record.dna),
        created_at=record.created_at,
    )
