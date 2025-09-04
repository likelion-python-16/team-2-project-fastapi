"""
Add social login fields to users

Revision ID: 20250830_add_social_login_fields
Revises: 20250829_add_round_reward_fields
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = '20250830_add_social_login_fields'
down_revision = '20250829_add_round_reward_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('provider', sa.String(length=20), nullable=True))
        batch.add_column(sa.Column('provider_id', sa.String(length=128), nullable=True))
        batch.add_column(sa.Column('birth_year', sa.String(length=10), nullable=True))
        batch.create_index('ix_users_provider', ['provider'])
        batch.create_index('ix_users_provider_id', ['provider_id'])
    op.create_unique_constraint('uq_user_provider_pid', 'users', ['provider', 'provider_id'])


def downgrade() -> None:
    op.drop_constraint('uq_user_provider_pid', 'users', type_='unique')
    with op.batch_alter_table('users') as batch:
        batch.drop_index('ix_users_provider')
        batch.drop_index('ix_users_provider_id')
        batch.drop_column('birth_year')
        batch.drop_column('provider_id')
        batch.drop_column('provider')

