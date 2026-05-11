"""rename value_mt_co2e to value_t_co2e

Revision ID: a27e000535e7
Revises: g8h9i0j1k2l3
Create Date: 2026-04-27 22:42:31.564640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a27e000535e7'
down_revision: Union[str, None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("emissions", "value_mt_co2e", new_column_name="value_t_co2e")
    op.alter_column("source_entries", "value_mt_co2e", new_column_name="value_t_co2e")
    op.alter_column("pledges", "baseline_value_mt_co2e", new_column_name="baseline_value_t_co2e")


def downgrade() -> None:
    op.alter_column("emissions", "value_t_co2e", new_column_name="value_mt_co2e")
    op.alter_column("source_entries", "value_t_co2e", new_column_name="value_mt_co2e")
    op.alter_column("pledges", "baseline_value_t_co2e", new_column_name="baseline_value_mt_co2e")
