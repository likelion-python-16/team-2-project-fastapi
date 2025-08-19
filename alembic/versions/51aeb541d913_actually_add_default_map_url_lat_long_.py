"""actually add default_map_url & lat/long to challenges

Revision ID: 51aeb541d913
Revises: 06111a89511a
Create Date: 2025-08-19 11:23:54.645505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51aeb541d913'
down_revision: Union[str, Sequence[str], None] = '06111a89511a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
