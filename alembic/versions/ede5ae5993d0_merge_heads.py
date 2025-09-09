"""merge heads

Revision ID: ede5ae5993d0
Revises: 0356e820adef, 69ff578363ef
Create Date: 2025-09-08 08:44:34.206028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ede5ae5993d0'
down_revision: Union[str, Sequence[str], None] = ('0356e820adef', '69ff578363ef')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
