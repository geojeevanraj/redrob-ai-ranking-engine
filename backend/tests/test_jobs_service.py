"""Job service tests (engine + repositories faked, no DB/LLM)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.jobs import JobIntelligenceEngine
from app.jobs.schema import JobExtractionMetadata, JobMetadata, JobProfile
from app.models.job import JobProfileRecord
from app.repositories.document import DocumentRepository
from app.repositories.job import JobRepository
from app.services.job_service import JobService
from tests.test_candidates_service import FakeDocumentRepo


def sample_profile() -> JobProfile:
    return JobProfile(
        job_metadata=JobMetadata(job_title="Backend Engineer", company_name="Acme"),
        required_skills=["Python"],
        technology_stack=["Python"],
        metadata=JobExtractionMetadata(
            extraction_confidence=0.83, llm_provider="gemini", llm_model="gemini-1.5-flash"
        ),
    )


class FakeJobEngine:
    def __init__(self, profile: JobProfile) -> None:
        self.profile = profile
        self.parsed_text: str | None = None

    async def parse(self, clean_text: str) -> JobProfile:
        self.parsed_text = clean_text
        return self.profile


class FakeJobRepo:
    def __init__(self) -> None:
        self.by_id: dict[uuid.UUID, JobProfileRecord] = {}

    async def add(self, record: JobProfileRecord) -> JobProfileRecord:
        if record.id is None:
            record.id = uuid.uuid4()
        record.created_at = datetime.now(UTC)
        self.by_id[record.id] = record
        return record

    async def get(self, job_id: uuid.UUID) -> JobProfileRecord | None:
        return self.by_id.get(job_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[JobProfileRecord]:
        return list(self.by_id.values())[offset : offset + limit]


def build_service(
    *, clean_text: str = "We are hiring a backend engineer..."
) -> tuple[JobService, object]:
    doc_repo = FakeDocumentRepo()
    doc = doc_repo.add_doc(clean_text=clean_text)
    service = JobService(
        cast(AsyncSession, object()),
        engine=cast(JobIntelligenceEngine, FakeJobEngine(sample_profile())),
        repository=cast(JobRepository, FakeJobRepo()),
        document_repository=cast(DocumentRepository, doc_repo),
    )
    return service, doc


async def test_parse_document_persists_profile() -> None:
    service, doc = build_service()
    record = await service.parse_document(doc.id)

    assert record.document_id == doc.id
    assert record.job_title == "Backend Engineer"
    assert record.company_name == "Acme"
    assert record.extraction_confidence == 0.83
    assert record.profile["required_skills"] == ["Python"]


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
