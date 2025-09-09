"""fix_nulls_and_add_is_superadmin

Revision ID: 877172f11b1f
Revises: fc7b0d47abe9
Create Date: 2025-09-08 14:28:11.147815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '877172f11b1f'
down_revision: Union[str, Sequence[str], None] = 'fc7b0d47abe9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix NULL values in challenges.min_participants before making it NOT NULL
    op.execute("UPDATE challenges SET min_participants = 1 WHERE min_participants IS NULL")
    
    # Add is_superadmin column to users table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col['name'] for col in inspector.get_columns('users')}
    if 'is_superadmin' not in existing_cols:
        op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_superadmin column from users table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col['name'] for col in inspector.get_columns('users')}
    if 'is_superadmin' in existing_cols:
        op.drop_column('users', 'is_superadmin')
    
    # Note: We don't revert the min_participants NULL fix as it would break data integrity
