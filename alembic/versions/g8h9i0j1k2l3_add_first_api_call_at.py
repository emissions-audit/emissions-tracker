"""Add first_api_call_at column to api_keys (ET-79)

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-04-19

Onboarding-funnel signal: stamped once by the first-call tracking middleware
on the first authenticated request per ApiKey. Remains NULL until then.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f7g8h9i0j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("first_api_call_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "first_api_call_at")
