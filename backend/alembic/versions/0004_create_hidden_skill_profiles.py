"""create hidden_skill_profiles table

Revision ID: 0004_create_hidden_skill_profiles
Revises: 0003_create_job_profiles
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_hidden_skills"
down_revision: str | None = "0003_create_job_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hidden_skill_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("skill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("profile", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_hidden_skill_profiles_candidate_id"),
        "hidden_skill_profiles",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_hidden_skill_profiles_candidate_id"),
        table_name="hidden_skill_profiles",
    )
    op.drop_table("hidden_skill_profiles")
