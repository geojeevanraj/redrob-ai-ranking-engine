"""create job_profiles table

Revision ID: 0003_create_job_profiles
Revises: 0002_create_candidate_profiles
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_create_job_profiles"
down_revision: str | None = "0002_create_candidate_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_title", sa.String(length=256), nullable=True),
        sa.Column("company_name", sa.String(length=256), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("profile", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_job_profiles_document_id"), "job_profiles", ["document_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_job_profiles_document_id"), table_name="job_profiles")
    op.drop_table("job_profiles")
