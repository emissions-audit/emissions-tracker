"""initial schema

Revision ID: 69d69119b891
Revises:
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "69d69119b891"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=True),
        sa.Column("sector", sa.String(length=50), nullable=False),
        sa.Column("subsector", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("use_case", sa.String(length=500), nullable=True),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("rate_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_call_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("api_key_hash", sa.String(length=16), nullable=True),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "filings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("filing_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("parser_used", sa.String(length=20), nullable=False),
        sa.Column("raw_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cross_validations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("max_value", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("spread_pct", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("flag", sa.String(length=10), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "emissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.Column("value_mt_co2e", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("methodology", sa.String(length=50), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "year", "scope", "source_id", name="uq_emission_source"),
    )

    op.create_table(
        "pledges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("pledge_type", sa.String(length=50), nullable=False),
        sa.Column("target_year", sa.Integer(), nullable=True),
        sa.Column("target_scope", sa.String(length=50), nullable=True),
        sa.Column("target_reduction_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("baseline_year", sa.Integer(), nullable=True),
        sa.Column("baseline_value_mt_co2e", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "data_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "source_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cross_validation_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("value_mt_co2e", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["cross_validation_id"], ["cross_validations.id"]),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("source_entries")
    op.drop_table("data_points")
    op.drop_table("pledges")
    op.drop_table("emissions")
    op.drop_table("cross_validations")
    op.drop_table("filings")
    op.drop_table("api_call_logs")
    op.drop_table("api_keys")
    op.drop_table("companies")
