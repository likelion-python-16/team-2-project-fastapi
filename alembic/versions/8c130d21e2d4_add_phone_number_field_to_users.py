"""add phone_number field to users

Revision ID: 8c130d21e2d4
Revises: 8c7726b28fa6
Create Date: 2025-08-19 11:46:09.228504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c130d21e2d4'
down_revision: Union[str, Sequence[str], None] = '8c7726b28fa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
