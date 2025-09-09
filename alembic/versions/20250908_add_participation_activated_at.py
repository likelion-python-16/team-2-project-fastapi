"""add activated_at to participations

Revision ID: add_participation_activated_at_20250908
Revises: add_participation_is_active_20250905
Create Date: 2025-09-08 23:20:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_participation_activated_at_20250908'
down_revision = 'add_participation_is_active_20250905'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add activated_at column to participations table
    op.add_column('participations', sa.Column('activated_at', sa.DateTime(), nullable=True, comment='실제 참가 시작 시간 (결제 완료 후)'))


def downgrade() -> None:
    # Remove activated_at column from participations table
    op.drop_column('participations', 'activated_at')