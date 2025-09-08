"""Add challenges.default_map_url (idempotent)

Revision ID: 20250907_add_default_map_url
Revises: 20250907_signup_enhancements
Create Date: 2025-09-07 00:00:10.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250907_add_default_map_url"
down_revision: Union[str, Sequence[str], None] = "20250907_signup_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("challenges", "default_map_url"):
        op.add_column("challenges", sa.Column("default_map_url", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("challenges", "default_map_url"):
        op.drop_column("challenges", "default_map_url")

