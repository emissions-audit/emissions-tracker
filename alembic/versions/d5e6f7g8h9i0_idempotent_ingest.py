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
    # Stage the filing dedup plan in a temp table so every step agrees on which
    # filing row "wins" per (company_id, year, filing_type).
    op.execute(
        """
        CREATE TEMP TABLE _filing_dedup ON COMMIT DROP AS
        SELECT id,
               FIRST_VALUE(id) OVER w AS keep_id,
               ROW_NUMBER() OVER w AS rn
        FROM filings
        WINDOW w AS (
            PARTITION BY company_id, year, filing_type
            ORDER BY created_at ASC, id ASC
        )
        """
    )

    # Collapse duplicate emissions first. If an emission on a duplicate filing
    # would collide with one already on the kept filing (same company/year/scope),
    # drop the dup; otherwise re-point it at the kept filing. Then apply the
    # existing uq_emission_source dedup to catch any remaining collisions.
    op.execute(
        """
        DELETE FROM emissions e
        USING _filing_dedup d
        WHERE e.source_id = d.id
          AND d.rn > 1
          AND EXISTS (
              SELECT 1 FROM emissions k
              WHERE k.source_id = d.keep_id
                AND k.company_id = e.company_id
                AND k.year = e.year
                AND k.scope = e.scope
          )
        """
    )
    op.execute(
        """
        UPDATE emissions e
        SET source_id = d.keep_id
        FROM _filing_dedup d
        WHERE e.source_id = d.id AND d.rn > 1
        """
    )
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

    # Re-point pledges and source_entries; no unique constraints to respect.
    op.execute(
        """
        UPDATE pledges p
        SET source_id = d.keep_id
        FROM _filing_dedup d
        WHERE p.source_id = d.id AND d.rn > 1
        """
    )
    op.execute(
        """
        UPDATE source_entries s
        SET filing_id = d.keep_id
        FROM _filing_dedup d
        WHERE s.filing_id = d.id AND d.rn > 1
        """
    )

    # Delete the superseded filing rows.
    op.execute(
        """
        DELETE FROM filings
        USING _filing_dedup d
        WHERE filings.id = d.id AND d.rn > 1
        """
    )

    op.create_unique_constraint(
        "uq_filing_natural_key",
        "filings",
        ["company_id", "year", "filing_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_filing_natural_key", "filings", type_="unique")
