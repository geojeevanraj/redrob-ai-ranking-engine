"""Document upload + retrieval endpoints.

POST /documents/upload   accept a file (multipart/form-data), process it
                         through the Document Intelligence Engine, and persist.
GET  /documents          list processed documents.
GET  /documents/{id}     fetch a single document (with clean text).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.exceptions import NotFoundError
from app.dependencies import DocumentServiceDep
from app.schemas.document import (
    DocumentDetail,
    DocumentRead,
    DocumentUploadResponse,
    to_detail,
    to_read,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a document",
)
async def upload_document(
    service: DocumentServiceDep,
    file: UploadFile = File(...),
    document_type: str = Form("unknown"),
) -> DocumentUploadResponse:
    """Upload a PDF/DOCX/TXT file and convert it into a canonical document."""
    content = await file.read()
    record, duplicate = await service.upload(
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        document_type=document_type,
    )
    return DocumentUploadResponse(document=to_read(record), duplicate=duplicate)


@router.get("", response_model=list[DocumentRead], summary="List documents")
async def list_documents(
    service: DocumentServiceDep,
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentRead]:
    records = await service.list(limit=limit, offset=offset)
    return [to_read(r) for r in records]


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get a document")
async def get_document(document_id: uuid.UUID, service: DocumentServiceDep) -> DocumentDetail:
    record = await service.get(document_id)
    if record is None:
        raise NotFoundError(f"Document {document_id} not found")
    return to_detail(record)
