"""Job parsing + retrieval endpoints.

POST /jobs/parse/{document_id}  parse a stored document into a job profile
GET  /jobs                      list job profiles
GET  /jobs/{job_id}             fetch a job profile
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.exceptions import NotFoundError
from app.dependencies import JobServiceDep
from app.schemas.job import JobProfileRead, JobSummary, to_read, to_summary

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/parse/{document_id}",
    response_model=JobProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Parse a document into a job profile",
)
async def parse_document(document_id: uuid.UUID, service: JobServiceDep) -> JobProfileRead:
    """Convert a previously uploaded job description into a structured profile."""
    record = await service.parse_document(document_id)
    return to_read(record)


@router.get("", response_model=list[JobSummary], summary="List job profiles")
async def list_jobs(service: JobServiceDep, limit: int = 50, offset: int = 0) -> list[JobSummary]:
    records = await service.list(limit=limit, offset=offset)
    return [to_summary(r) for r in records]


@router.get("/{job_id}", response_model=JobProfileRead, summary="Get a job profile")
async def get_job(job_id: uuid.UUID, service: JobServiceDep) -> JobProfileRead:
    record = await service.get(job_id)
    if record is None:
        raise NotFoundError(f"Job {job_id} not found")
    return to_read(record)
