"""Add coverage_snapshots table

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b3c4d5e6f7g8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coverage_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("source_filter", sa.String(50), nullable=True),
        sa.Column("total_companies", sa.Integer(), nullable=False),
        sa.Column("total_emissions", sa.Integer(), nullable=False),
        sa.Column("total_filings", sa.Integer(), nullable=False),
        sa.Column("total_cross_validations", sa.Integer(), nullable=False),
        sa.Column("year_min", sa.Integer(), nullable=True),
        sa.Column("year_max", sa.Integer(), nullable=True),
        sa.Column("by_source_year", JSONB(), nullable=False),
        sa.Column("by_company_source", JSONB(), nullable=False),
        sa.Column("by_company_year", JSONB(), nullable=False),
        sa.Column("cv_by_flag", JSONB(), nullable=False),
        sa.Column("cv_coverage_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("alerts", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("coverage_snapshots")
