"""Explanation repository."""

from __future__ import annotations

import uuid

from app.models.explanation import ExplanationRecord
from app.repositories.base import BaseRepository


class ExplanationRepository(BaseRepository[ExplanationRecord]):
    """Persistence access for explanations."""

    async def add(self, record: ExplanationRecord) -> ExplanationRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, explanation_id: uuid.UUID) -> ExplanationRecord | None:
        return await self.session.get(ExplanationRecord, explanation_id)
