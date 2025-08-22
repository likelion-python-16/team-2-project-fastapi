"""add default_map_url & lat/long to challenges

Revision ID: 1b36dcc492a9
Revises: dd6bdf057ac0
Create Date: 2025-08-19 11:13:30.185528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b36dcc492a9'
down_revision: Union[str, Sequence[str], None] = 'dd6bdf057ac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
