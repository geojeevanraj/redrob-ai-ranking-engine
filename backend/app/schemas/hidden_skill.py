"""Hidden skill API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.hidden_skills.model import HiddenSkillProfile
from app.models.hidden_skill import HiddenSkillProfileRecord


class HiddenSkillProfileRead(BaseModel):
    """Full view of a persisted hidden-skill profile."""

    id: str
    candidate_id: str
    skill_count: int
    llm_provider: str | None
    llm_model: str | None
    profile: HiddenSkillProfile
    created_at: datetime


def to_read(record: HiddenSkillProfileRecord) -> HiddenSkillProfileRead:
    return HiddenSkillProfileRead(
        id=str(record.id),
        candidate_id=str(record.candidate_id),
        skill_count=record.skill_count,
        llm_provider=record.llm_provider,
        llm_model=record.llm_model,
        profile=HiddenSkillProfile.model_validate(record.profile),
        created_at=record.created_at,
    )
