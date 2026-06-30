"""Job Profile ORM model.

Persisted separately from `DocumentRecord` but linked to it by `document_id`.
The full structured `JobProfile` is stored as JSONB; a few fields are promoted
to columns for cheap querying/listing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobProfileRecord(Base):
    """A structured job profile derived from a document."""

    __tablename__ = "job_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Promoted fields for listing/search.
    job_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Full structured profile.
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
