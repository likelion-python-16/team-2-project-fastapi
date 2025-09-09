"""Re-add challenges.cover_image_url if missing (idempotent)

Revision ID: 20250908_readd_cover_image_url
Revises: ede5ae5993d0
Create Date: 2025-09-08 20:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250908_readd_cover_image_url"
down_revision: Union[str, Sequence[str], None] = "ede5ae5993d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("challenges", "cover_image_url"):
        op.add_column("challenges", sa.Column("cover_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("challenges", "cover_image_url"):
        op.drop_column("challenges", "cover_image_url")

