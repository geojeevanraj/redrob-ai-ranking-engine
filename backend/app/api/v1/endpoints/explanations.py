"""Explainability endpoints.

POST /explanations/generate   explain a decision + persist
POST /explanations/compare    compare two decisions
GET  /explanations/{id}        fetch an explanation
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import ExplanationServiceDep
from app.schemas.explanation import (
    CompareRequest,
    ComparisonResponse,
    ExplanationRead,
    GenerateRequest,
    to_read,
)

router = APIRouter(prefix="/explanations", tags=["explanations"])


@router.post(
    "/generate",
    response_model=ExplanationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an evidence-backed explanation for a decision",
)
async def generate(payload: GenerateRequest, service: ExplanationServiceDep) -> ExplanationRead:
    record = await service.generate(payload.decision_id)
    return to_read(record)


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare two hiring decisions",
)
async def compare(payload: CompareRequest, service: ExplanationServiceDep) -> ComparisonResponse:
    comparison = await service.compare(payload.decision_id_a, payload.decision_id_b)
    return ComparisonResponse(comparison=comparison)


@router.get("/{explanation_id}", response_model=ExplanationRead, summary="Get an explanation")
async def get_explanation(
    explanation_id: uuid.UUID, service: ExplanationServiceDep
) -> ExplanationRead:
    record = await service.get(explanation_id)
    return to_read(record)
