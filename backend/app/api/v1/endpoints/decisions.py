"""Decision Intelligence endpoints.

POST /decisions/evaluate     compare a candidate to a job + persist
GET  /decisions              list decisions (filter by candidate/job)
GET  /decisions/{id}         fetch a decision
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import DecisionServiceDep
from app.schemas.decision import DecisionRead, DecisionSummary, EvaluateRequest, to_read, to_summary

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.post(
    "/evaluate",
    response_model=DecisionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a candidate against a job",
)
async def evaluate(payload: EvaluateRequest, service: DecisionServiceDep) -> DecisionRead:
    record = await service.evaluate(
        payload.candidate_id, payload.job_id, weighting_profile=payload.weighting_profile
    )
    return to_read(record)


@router.get("", response_model=list[DecisionSummary], summary="List decisions")
async def list_decisions(
    service: DecisionServiceDep,
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DecisionSummary]:
    records = await service.list(
        candidate_id=candidate_id, job_id=job_id, limit=limit, offset=offset
    )
    return [to_summary(r) for r in records]


@router.get("/{decision_id}", response_model=DecisionRead, summary="Get a decision")
async def get_decision(decision_id: uuid.UUID, service: DecisionServiceDep) -> DecisionRead:
    record = await service.get(decision_id)
    return to_read(record)
