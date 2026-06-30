"""Hidden skill profile repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.hidden_skill import HiddenSkillProfileRecord
from app.repositories.base import BaseRepository


class HiddenSkillRepository(BaseRepository[HiddenSkillProfileRecord]):
    """Persistence access for hidden-skill profiles."""

    async def add(self, record: HiddenSkillProfileRecord) -> HiddenSkillProfileRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, profile_id: uuid.UUID) -> HiddenSkillProfileRecord | None:
        return await self.session.get(HiddenSkillProfileRecord, profile_id)

    async def get_latest_for_candidate(
        self, candidate_id: uuid.UUID
    ) -> HiddenSkillProfileRecord | None:
        result = await self.session.execute(
            select(HiddenSkillProfileRecord)
            .where(HiddenSkillProfileRecord.candidate_id == candidate_id)
            .order_by(HiddenSkillProfileRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_candidate(
        self, candidate_id: uuid.UUID
    ) -> Sequence[HiddenSkillProfileRecord]:
        result = await self.session.execute(
            select(HiddenSkillProfileRecord)
            .where(HiddenSkillProfileRecord.candidate_id == candidate_id)
            .order_by(HiddenSkillProfileRecord.created_at.desc())
        )
        return result.scalars().all()
