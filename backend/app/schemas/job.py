"""Job API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.jobs.schema import JobProfile
from app.models.job import JobProfileRecord


class JobSummary(BaseModel):
    """Lightweight view for listings."""

    id: str
    document_id: str
    job_title: str | None
    company_name: str | None
    extraction_confidence: float
    created_at: datetime


class JobProfileRead(JobSummary):
    """Full view including the structured profile and LLM provenance."""

    llm_provider: str | None
    llm_model: str | None
    profile: JobProfile


def to_summary(record: JobProfileRecord) -> JobSummary:
    return JobSummary(
        id=str(record.id),
        document_id=str(record.document_id),
        job_title=record.job_title,
        company_name=record.company_name,
        extraction_confidence=record.extraction_confidence,
        created_at=record.created_at,
    )


def to_read(record: JobProfileRecord) -> JobProfileRead:
    return JobProfileRead(
        id=str(record.id),
        document_id=str(record.document_id),
        job_title=record.job_title,
        company_name=record.company_name,
        extraction_confidence=record.extraction_confidence,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        profile=JobProfile.model_validate(record.profile),
        created_at=record.created_at,
    )
