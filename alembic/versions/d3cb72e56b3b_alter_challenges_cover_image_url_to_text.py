"""alter challenges.cover_image_url to TEXT

Revision ID: d3cb72e56b3b
Revises: 8e2a3c1d8b0b
Create Date: 2025-09-05 10:54:58.037181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3cb72e56b3b'
down_revision: Union[str, Sequence[str], None] = '8e2a3c1d8b0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
