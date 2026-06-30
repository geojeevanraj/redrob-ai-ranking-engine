"""create documents table

Revision ID: 0001_create_documents
Revises:
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_documents"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("language_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("text_extraction_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("empty_page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("malformed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "processing_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("clean_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_documents_checksum"), "documents", ["checksum"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_checksum"), table_name="documents")
    op.drop_table("documents")
