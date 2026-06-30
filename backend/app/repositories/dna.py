"""Candidate DNA repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.dna import CandidateDNARecord
from app.repositories.base import BaseRepository


class DNARepository(BaseRepository[CandidateDNARecord]):
    """Persistence access for candidate DNA profiles."""

    async def add(self, record: CandidateDNARecord) -> CandidateDNARecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_latest_for_candidate(self, candidate_id: uuid.UUID) -> CandidateDNARecord | None:
        result = await self.session.execute(
            select(CandidateDNARecord)
            .where(CandidateDNARecord.candidate_id == candidate_id)
            .order_by(CandidateDNARecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
