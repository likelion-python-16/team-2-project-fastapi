"""add default_place_id to challenges

Revision ID: 3b2f0e7a2f3a
Revises: a7f2d9c8b3a1
Create Date: 2025-09-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b2f0e7a2f3a'
down_revision = 'a7f2d9c8b3a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('challenges', sa.Column('default_place_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('challenges', 'default_place_id')

