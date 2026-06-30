"""create explanations table

Revision ID: 0007_create_explanations
Revises: 0006_create_decisions
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_create_explanations"
down_revision: str | None = "0006_create_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "explanations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("decision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("explanation", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_explanations_decision_id"), "explanations", ["decision_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_explanations_decision_id"), table_name="explanations")
    op.drop_table("explanations")
