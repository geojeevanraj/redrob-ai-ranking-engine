"""Job service — parse a stored document into a persisted job profile.

Flow:
    fetch DocumentRecord (already extracted/cleaned in Sprint 1.2)
    -> run Job Intelligence Engine on its clean text
    -> persist JobProfileRecord linked to the document
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.jobs import JobIntelligenceEngine
from app.models.job import JobProfileRecord
from app.repositories.document import DocumentRepository
from app.repositories.job import JobRepository
from app.services.base import BaseService


class JobService(BaseService):
    """Coordinates job-description parsing and job-profile persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: JobIntelligenceEngine,
        repository: JobRepository | None = None,
        document_repository: DocumentRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or JobRepository(session)
        self.documents = document_repository or DocumentRepository(session)

    async def parse_document(self, document_id: uuid.UUID) -> JobProfileRecord:
        """Parse a previously uploaded document into a job profile."""
        document = await self.documents.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        if not document.clean_text or not document.clean_text.strip():
            raise ValidationError("Document has no extractable text to parse")

        profile = await self.engine.parse(document.clean_text)
        record = JobProfileRecord(
            document_id=document.id,
            job_title=profile.job_metadata.job_title,
            company_name=profile.job_metadata.company_name,
            extraction_confidence=profile.metadata.extraction_confidence,
            llm_provider=profile.metadata.llm_provider,
            llm_model=profile.metadata.llm_model,
            profile=profile.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def get(self, job_id: uuid.UUID) -> JobProfileRecord | None:
        return await self.repo.get(job_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[JobProfileRecord]:
        return list(await self.repo.list(limit=limit, offset=offset))
