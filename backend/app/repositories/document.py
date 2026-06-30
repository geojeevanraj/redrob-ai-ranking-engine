"""Document repository — persistence access for `DocumentRecord`."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.document import DocumentRecord
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[DocumentRecord]):
    """Encapsulates all queries for processed documents."""

    async def add(self, document: DocumentRecord) -> DocumentRecord:
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def get(self, document_id: uuid.UUID) -> DocumentRecord | None:
        return await self.session.get(DocumentRecord, document_id)

    async def get_by_checksum(self, checksum: str) -> DocumentRecord | None:
        result = await self.session.execute(
            select(DocumentRecord).where(DocumentRecord.checksum == checksum)
        )
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0) -> Sequence[DocumentRecord]:
        result = await self.session.execute(
            select(DocumentRecord)
            .order_by(DocumentRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
