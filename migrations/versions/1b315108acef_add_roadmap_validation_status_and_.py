"""add_roadmap_validation_status_and_evaluator_fields

Revision ID: 1b315108acef
Revises: 881408fd6535
Create Date: 2026-09-07 20:04:04.824770

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1b315108acef'
down_revision: str | None = '881408fd6535'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("roadmaps", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("validation_status", sa.String(length=50), nullable=False, server_default="COMPLETED")
        )
        batch_op.add_column(
            sa.Column("evaluator_score", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("evaluator_verdict", sa.String(length=20), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("roadmaps", schema=None) as batch_op:
        batch_op.drop_column("evaluator_verdict")
        batch_op.drop_column("evaluator_score")
        batch_op.drop_column("validation_status")
