"""add is_active to participations with default

Revision ID: add_participation_is_active_20250905
Revises: 0a0b993352f5
Create Date: 2025-09-05 00:10:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_participation_is_active_20250905'
down_revision = '0a0b993352f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL: add column with default and not null, then backfill existing
    op.add_column('participations', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('1')))
    # Ensure NOT NULL after backfill
    op.execute("UPDATE participations SET is_active = 1 WHERE is_active IS NULL")
    op.alter_column('participations', 'is_active', existing_type=sa.Boolean(), nullable=False)
    op.create_index('ix_participation_is_active', 'participations', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_participation_is_active', table_name='participations')
    op.drop_column('participations', 'is_active')

