"""Candidate DNA endpoints.

POST /candidates/{candidate_id}/dna   compute + persist DNA profile
GET  /candidates/{candidate_id}/dna   fetch latest DNA profile
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import DNAServiceDep
from app.schemas.dna import CandidateDNARead, to_read

router = APIRouter(prefix="/candidates", tags=["candidate-dna"])


@router.post(
    "/{candidate_id}/dna",
    response_model=CandidateDNARead,
    status_code=status.HTTP_201_CREATED,
    summary="Compute a candidate's professional DNA",
)
async def generate_dna(candidate_id: uuid.UUID, service: DNAServiceDep) -> CandidateDNARead:
    record = await service.generate(candidate_id)
    return to_read(record)


@router.get(
    "/{candidate_id}/dna",
    response_model=CandidateDNARead,
    summary="Get a candidate's latest DNA profile",
)
async def get_dna(candidate_id: uuid.UUID, service: DNAServiceDep) -> CandidateDNARead:
    record = await service.get_latest(candidate_id)
    return to_read(record)
