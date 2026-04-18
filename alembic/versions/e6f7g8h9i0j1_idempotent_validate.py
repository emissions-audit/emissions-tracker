"""Add unique constraint on cross_validations natural key for idempotent validate

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e6f7g8h9i0j1"
down_revision: Union[str, None] = "d5e6f7g8h9i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate cross_validations: keep the latest row per (company_id, year, scope).
    # First, delete source_entries pointing at duplicate CVs that will be removed.
    op.execute(
        """
        CREATE TEMP TABLE _cv_dedup ON COMMIT DROP AS
        SELECT id,
               FIRST_VALUE(id) OVER w AS keep_id,
               ROW_NUMBER() OVER w AS rn
        FROM cross_validations
        WINDOW w AS (
            PARTITION BY company_id, year, scope
            ORDER BY updated_at DESC, id ASC
        )
        """
    )

    # Re-point source_entries from duplicate CVs to the kept CV.
    # If a source_entry on a dup CV would collide (same source_type on the kept CV),
    # delete the dup entry; otherwise re-point it.
    op.execute(
        """
        DELETE FROM source_entries se
        USING _cv_dedup d
        WHERE se.cross_validation_id = d.id
          AND d.rn > 1
          AND EXISTS (
              SELECT 1 FROM source_entries k
              WHERE k.cross_validation_id = d.keep_id
                AND k.source_type = se.source_type
          )
        """
    )
    op.execute(
        """
        UPDATE source_entries se
        SET cross_validation_id = d.keep_id
        FROM _cv_dedup d
        WHERE se.cross_validation_id = d.id AND d.rn > 1
        """
    )

    # Delete the duplicate cross_validation rows.
    op.execute(
        """
        DELETE FROM cross_validations
        USING _cv_dedup d
        WHERE cross_validations.id = d.id AND d.rn > 1
        """
    )

    op.create_unique_constraint(
        "uq_cv_natural_key",
        "cross_validations",
        ["company_id", "year", "scope"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_cv_natural_key", "cross_validations", type_="unique")
