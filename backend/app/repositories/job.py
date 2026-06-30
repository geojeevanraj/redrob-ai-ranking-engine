"""Job profile repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.job import JobProfileRecord
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobProfileRecord]):
    """Persistence access for job profiles."""

    async def add(self, record: JobProfileRecord) -> JobProfileRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, job_id: uuid.UUID) -> JobProfileRecord | None:
        return await self.session.get(JobProfileRecord, job_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> Sequence[JobProfileRecord]:
        result = await self.session.execute(
            select(JobProfileRecord)
            .order_by(JobProfileRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
