"""Candidate service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates import CandidateIntelligenceEngine
from app.candidates.schema import CandidateProfile, ExtractionMetadata, PersonalInfo
from app.core.exceptions import NotFoundError, ValidationError
from app.models.candidate import CandidateProfileRecord
from app.models.document import DocumentRecord
from app.repositories.candidate import CandidateRepository
from app.repositories.document import DocumentRepository
from app.services.candidate_service import CandidateService


def sample_profile() -> CandidateProfile:
    return CandidateProfile(
        personal_info=PersonalInfo(full_name="Ada Lovelace", email="ada@x.io"),
        technology_stack=["Python"],
        metadata=ExtractionMetadata(
            extraction_confidence=0.86, llm_provider="gemini", llm_model="gemini-1.5-flash"
        ),
    )


class FakeEngine:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile
        self.parsed_text: str | None = None

    async def parse(self, clean_text: str) -> CandidateProfile:
        self.parsed_text = clean_text
        return self.profile


class FakeCandidateRepo:
    def __init__(self) -> None:
        self.by_id: dict[uuid.UUID, CandidateProfileRecord] = {}

    async def add(self, record: CandidateProfileRecord) -> CandidateProfileRecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.by_id[record.id] = record
        return record

    async def get(self, candidate_id: uuid.UUID) -> CandidateProfileRecord | None:
        return self.by_id.get(candidate_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[CandidateProfileRecord]:
        return list(self.by_id.values())[offset : offset + limit]


class FakeDocumentRepo:
    def __init__(self) -> None:
        self.by_id: dict[uuid.UUID, DocumentRecord] = {}

    def add_doc(self, *, clean_text: str) -> DocumentRecord:
        doc = DocumentRecord(
            id=uuid.uuid4(),
            filename="r.txt",
            document_type="resume",
            extension="txt",
            mime_type="text/plain",
            file_size=10,
            checksum=uuid.uuid4().hex,
            storage_path="/tmp/r.txt",
            clean_text=clean_text,
            raw_text=clean_text,
        )
        self.by_id[doc.id] = doc
        return doc

    async def get(self, document_id: uuid.UUID) -> DocumentRecord | None:
        return self.by_id.get(document_id)


def build_service(
    *, clean_text: str = "Ada Lovelace resume content"
) -> tuple[CandidateService, DocumentRecord]:
    doc_repo = FakeDocumentRepo()
    doc = doc_repo.add_doc(clean_text=clean_text)
    service = CandidateService(
        cast(AsyncSession, object()),
        engine=cast(CandidateIntelligenceEngine, FakeEngine(sample_profile())),
        repository=cast(CandidateRepository, FakeCandidateRepo()),
        document_repository=cast(DocumentRepository, doc_repo),
    )
    return service, doc


async def test_parse_document_persists_profile() -> None:
    service, doc = build_service()
    record = await service.parse_document(doc.id)

    assert record.document_id == doc.id
    assert record.full_name == "Ada Lovelace"
    assert record.email == "ada@x.io"
    assert record.extraction_confidence == 0.86
    assert record.profile["personal_info"]["full_name"] == "Ada Lovelace"


async def test_parse_missing_document_raises() -> None:
    service, _ = build_service()
    with pytest.raises(NotFoundError):
        await service.parse_document(uuid.uuid4())


async def test_parse_empty_document_raises() -> None:
    service, doc = build_service(clean_text="   ")
    with pytest.raises(ValidationError):
        await service.parse_document(doc.id)


async def test_get_and_list() -> None:
    service, doc = build_service()
    record = await service.parse_document(doc.id)

    fetched = await service.get(record.id)
    assert fetched is not None
    listing = await service.list()
    assert any(r.id == record.id for r in listing)
