"""add default_map_url & lat/long to challenges

Revision ID: 06111a89511a
Revises: 1b36dcc492a9
Create Date: 2025-08-19 11:14:30.091720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06111a89511a'
down_revision: Union[str, Sequence[str], None] = '1b36dcc492a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
