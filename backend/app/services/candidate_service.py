"""Candidate service — parse a stored document into a persisted profile.

Flow:
    fetch DocumentRecord (already extracted/cleaned in Sprint 1.2)
    -> run Candidate Intelligence Engine on its clean text
    -> persist CandidateProfileRecord linked to the document
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates import CandidateIntelligenceEngine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.candidate import CandidateProfileRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.document import DocumentRepository
from app.services.base import BaseService


class CandidateService(BaseService):
    """Coordinates resume parsing and candidate-profile persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        engine: CandidateIntelligenceEngine,
        repository: CandidateRepository | None = None,
        document_repository: DocumentRepository | None = None,
    ) -> None:
        super().__init__(session)
        self.engine = engine
        self.repo = repository or CandidateRepository(session)
        self.documents = document_repository or DocumentRepository(session)

    async def parse_document(self, document_id: uuid.UUID) -> CandidateProfileRecord:
        """Parse a previously uploaded document into a candidate profile."""
        document = await self.documents.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        if not document.clean_text or not document.clean_text.strip():
            raise ValidationError("Document has no extractable text to parse")

        profile = await self.engine.parse(document.clean_text)
        record = CandidateProfileRecord(
            document_id=document.id,
            full_name=profile.personal_info.full_name,
            email=profile.personal_info.email,
            extraction_confidence=profile.metadata.extraction_confidence,
            llm_provider=profile.metadata.llm_provider,
            llm_model=profile.metadata.llm_model,
            profile=profile.model_dump(mode="json"),
        )
        return await self.repo.add(record)

    async def get(self, candidate_id: uuid.UUID) -> CandidateProfileRecord | None:
        return await self.repo.get(candidate_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[CandidateProfileRecord]:
        return list(await self.repo.list(limit=limit, offset=offset))
