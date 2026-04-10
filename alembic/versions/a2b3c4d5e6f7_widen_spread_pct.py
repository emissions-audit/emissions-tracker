"""Widen spread_pct column precision

Revision ID: a2b3c4d5e6f7
Revises: 69d69119b891
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "69d69119b891"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "cross_validations",
        "spread_pct",
        type_=sa.Numeric(precision=12, scale=2),
        existing_type=sa.Numeric(precision=8, scale=2),
    )


def downgrade() -> None:
    op.alter_column(
        "cross_validations",
        "spread_pct",
        type_=sa.Numeric(precision=8, scale=2),
        existing_type=sa.Numeric(precision=12, scale=2),
    )
