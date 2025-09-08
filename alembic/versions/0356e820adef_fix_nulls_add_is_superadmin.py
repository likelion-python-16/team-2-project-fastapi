"""fix NULLs & add is_superadmin

Revision ID: 0356e820adef
Revises: 877172f11b1f
Create Date: 2025-09-08 14:52:44.289107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0356e820adef'
down_revision: Union[str, Sequence[str], None] = '877172f11b1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
