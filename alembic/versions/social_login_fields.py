"""add social login fields to users

Revision ID: social_login_fields
Revises: email_verifications
Create Date: 2025-09-02 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'social_login_fields'
down_revision: Union[str, Sequence[str], None] = 'email_verifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add social login fields to users table
    op.add_column('users', sa.Column('provider', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('provider_id', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('birth_year', sa.String(length=10), nullable=True))
    
    # Create indexes for social login fields
    op.create_index(op.f('ix_users_provider'), 'users', ['provider'], unique=False)
    op.create_index(op.f('ix_users_provider_id'), 'users', ['provider_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_users_provider_id'), table_name='users')
    op.drop_index(op.f('ix_users_provider'), table_name='users')
    
    # Drop columns
    op.drop_column('users', 'birth_year')
    op.drop_column('users', 'provider_id')
    op.drop_column('users', 'provider')