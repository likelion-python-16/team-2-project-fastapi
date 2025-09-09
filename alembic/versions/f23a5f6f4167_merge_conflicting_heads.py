"""merge conflicting heads

Revision ID: f23a5f6f4167
Revises: abc123456789, dd6bdf057ac0
Create Date: 2025-09-04 02:20:56.136667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f23a5f6f4167'
down_revision: Union[str, Sequence[str], None] = ('abc123456789', 'dd6bdf057ac0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
