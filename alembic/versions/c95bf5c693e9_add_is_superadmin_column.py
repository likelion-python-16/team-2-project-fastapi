"""add_is_superadmin_column

Revision ID: c95bf5c693e9
Revises: 724acfd982f4
Create Date: 2025-09-08 13:37:17.587007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c95bf5c693e9'
down_revision: Union[str, Sequence[str], None] = '724acfd982f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col['name'] for col in inspector.get_columns('users')}
    if 'is_superadmin' not in existing_cols:
        op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_superadmin')
