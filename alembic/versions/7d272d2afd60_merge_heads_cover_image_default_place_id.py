"""merge heads: cover_image + default_place_id

Revision ID: 7d272d2afd60
Revises: add_challenge_default_place_id, add_challenge_cover_image
Create Date: 2025-08-28 18:51:51.474435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d272d2afd60'
down_revision: Union[str, Sequence[str], None] = ('add_challenge_default_place_id', 'add_challenge_cover_image')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
