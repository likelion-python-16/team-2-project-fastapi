"""add social login fields to users

Revision ID: social_login_fields
Revises: email_verifications
Create Date: 2025-09-02 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'social_login_fields'
down_revision: Union[str, Sequence[str], None] = 'email_verifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with idempotency guards."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Skip if users table missing (defensive)
    if not inspector.has_table('users'):
        return

    existing_cols = {c['name'] for c in inspector.get_columns('users')}

    # Add social login fields if absent
    if 'provider' not in existing_cols:
        op.add_column('users', sa.Column('provider', sa.String(length=20), nullable=True))
    if 'provider_id' not in existing_cols:
        op.add_column('users', sa.Column('provider_id', sa.String(length=128), nullable=True))
    if 'birth_year' not in existing_cols:
        op.add_column('users', sa.Column('birth_year', sa.String(length=10), nullable=True))
    
    # Create indexes for social login fields if missing
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}
    if 'ix_users_provider' not in existing_indexes:
        op.create_index(op.f('ix_users_provider'), 'users', ['provider'], unique=False)
    if 'ix_users_provider_id' not in existing_indexes:
        op.create_index(op.f('ix_users_provider_id'), 'users', ['provider_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema with guards."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table('users'):
        return

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}
    if 'ix_users_provider_id' in existing_indexes:
        op.drop_index(op.f('ix_users_provider_id'), table_name='users')
    if 'ix_users_provider' in existing_indexes:
        op.drop_index(op.f('ix_users_provider'), table_name='users')

    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'birth_year' in cols:
        op.drop_column('users', 'birth_year')
    if 'provider_id' in cols:
        op.drop_column('users', 'provider_id')
    if 'provider' in cols:
        op.drop_column('users', 'provider')
