"""Add unique constraint on filings natural key for idempotent ingest

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-04-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d5e6f7g8h9i0"
down_revision: Union[str, None] = "c4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Collapse pre-existing duplicate filings (keep the oldest row per natural key)
    # so the unique constraint can be applied without failure. Emissions pointing
    # at superseded filing rows are re-pointed at the surviving filing.
    op.execute(
        """
        WITH ranked AS (
            SELECT id, company_id, year, filing_type,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS rn,
                   FIRST_VALUE(id) OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS keep_id
            FROM filings
        )
        UPDATE emissions e
        SET source_id = r.keep_id
        FROM ranked r
        WHERE e.source_id = r.id AND r.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, company_id, year, filing_type,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS rn,
                   FIRST_VALUE(id) OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS keep_id
            FROM filings
        )
        UPDATE pledges p
        SET source_id = r.keep_id
        FROM ranked r
        WHERE p.source_id = r.id AND r.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, company_id, year, filing_type,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS rn,
                   FIRST_VALUE(id) OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS keep_id
            FROM filings
        )
        UPDATE source_entries s
        SET filing_id = r.keep_id
        FROM ranked r
        WHERE s.filing_id = r.id AND r.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, year, filing_type
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM filings
        )
        DELETE FROM filings USING ranked
        WHERE filings.id = ranked.id AND ranked.rn > 1
        """
    )

    # Deduplicate emissions that collide on the existing uq_emission_source
    # constraint (can happen if multiple fresh-UUID inserts shared a filing).
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, year, scope, source_id
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM emissions
            WHERE source_id IS NOT NULL
        )
        DELETE FROM emissions USING ranked
        WHERE emissions.id = ranked.id AND ranked.rn > 1
        """
    )

    op.create_unique_constraint(
        "uq_filing_natural_key",
        "filings",
        ["company_id", "year", "filing_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_filing_natural_key", "filings", type_="unique")
