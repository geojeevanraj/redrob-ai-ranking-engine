"""create decisions table

Revision ID: 0006_create_decisions
Revises: 0005_create_candidate_dna
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_create_decisions"
down_revision: str | None = "0005_create_candidate_dna"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("overall_match_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("weighting_profile", sa.String(length=64), nullable=False),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("decision", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_decisions_candidate_id"), "decisions", ["candidate_id"])
    op.create_index(op.f("ix_decisions_job_id"), "decisions", ["job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_decisions_job_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_candidate_id"), table_name="decisions")
    op.drop_table("decisions")
