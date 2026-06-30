"""Candidate profile repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.candidate import CandidateProfileRecord
from app.repositories.base import BaseRepository


class CandidateRepository(BaseRepository[CandidateProfileRecord]):
    """Persistence access for candidate profiles."""

    async def add(self, record: CandidateProfileRecord) -> CandidateProfileRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, candidate_id: uuid.UUID) -> CandidateProfileRecord | None:
        return await self.session.get(CandidateProfileRecord, candidate_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> Sequence[CandidateProfileRecord]:
        result = await self.session.execute(
            select(CandidateProfileRecord)
            .order_by(CandidateProfileRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
