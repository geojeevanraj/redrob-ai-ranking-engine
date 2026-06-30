"""Candidate parsing + retrieval endpoints.

POST /candidates/parse/{document_id}  parse a stored document into a profile
GET  /candidates/{candidate_id}       fetch a candidate profile
GET  /candidates                      list candidate profiles
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.exceptions import NotFoundError
from app.dependencies import CandidateServiceDep
from app.schemas.candidate import CandidateProfileRead, CandidateSummary, to_read, to_summary

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post(
    "/parse/{document_id}",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Parse a document into a candidate profile",
)
async def parse_document(
    document_id: uuid.UUID, service: CandidateServiceDep
) -> CandidateProfileRead:
    """Convert a previously uploaded document into a structured profile."""
    record = await service.parse_document(document_id)
    return to_read(record)


@router.get("", response_model=list[CandidateSummary], summary="List candidate profiles")
async def list_candidates(
    service: CandidateServiceDep, limit: int = 50, offset: int = 0
) -> list[CandidateSummary]:
    records = await service.list(limit=limit, offset=offset)
    return [to_summary(r) for r in records]


@router.get(
    "/{candidate_id}",
    response_model=CandidateProfileRead,
    summary="Get a candidate profile",
)
async def get_candidate(
    candidate_id: uuid.UUID, service: CandidateServiceDep
) -> CandidateProfileRead:
    record = await service.get(candidate_id)
    if record is None:
        raise NotFoundError(f"Candidate {candidate_id} not found")
    return to_read(record)
