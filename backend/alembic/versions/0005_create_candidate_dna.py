"""create candidate_dna table

Revision ID: 0005_create_candidate_dna
Revises: 0004_create_hidden_skill_profiles
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_create_candidate_dna"
down_revision: str | None = "0004_hidden_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_dna",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("overall_focus", sa.String(length=128), nullable=True),
        sa.Column("top_archetype", sa.String(length=128), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("dna", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_candidate_dna_candidate_id"), "candidate_dna", ["candidate_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_candidate_dna_candidate_id"), table_name="candidate_dna")
    op.drop_table("candidate_dna")
