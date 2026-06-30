"""Decision repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.decision import DecisionRecord
from app.repositories.base import BaseRepository


class DecisionRepository(BaseRepository[DecisionRecord]):
    """Persistence access for hiring decisions."""

    async def add(self, record: DecisionRecord) -> DecisionRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, decision_id: uuid.UUID) -> DecisionRecord | None:
        return await self.session.get(DecisionRecord, decision_id)

    async def list(
        self,
        *,
        candidate_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DecisionRecord]:
        stmt = select(DecisionRecord).order_by(DecisionRecord.created_at.desc())
        if candidate_id is not None:
            stmt = stmt.where(DecisionRecord.candidate_id == candidate_id)
        if job_id is not None:
            stmt = stmt.where(DecisionRecord.job_id == job_id)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return result.scalars().all()
