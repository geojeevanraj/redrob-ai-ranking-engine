"""Hidden skill inference endpoints.

POST /candidates/{candidate_id}/infer-skills    run inference + persist
GET  /candidates/{candidate_id}/hidden-skills   fetch latest hidden-skill profile
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import HiddenSkillServiceDep
from app.schemas.hidden_skill import HiddenSkillProfileRead, to_read

router = APIRouter(prefix="/candidates", tags=["hidden-skills"])


@router.post(
    "/{candidate_id}/infer-skills",
    response_model=HiddenSkillProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Infer evidence-backed hidden skills for a candidate",
)
async def infer_skills(
    candidate_id: uuid.UUID, service: HiddenSkillServiceDep
) -> HiddenSkillProfileRead:
    record = await service.infer(candidate_id)
    return to_read(record)


@router.get(
    "/{candidate_id}/hidden-skills",
    response_model=HiddenSkillProfileRead,
    summary="Get a candidate's latest hidden-skill profile",
)
async def get_hidden_skills(
    candidate_id: uuid.UUID, service: HiddenSkillServiceDep
) -> HiddenSkillProfileRead:
    record = await service.get_latest(candidate_id)
    return to_read(record)
