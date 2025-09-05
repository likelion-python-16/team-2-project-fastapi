"""add default_map_url to challenges

Revision ID: add_default_map_url_to_challenges
Revises: 8e2a3c1d8b0f
Create Date: 2025-09-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'add_default_map_url_to_challenges'
down_revision = '8e2a3c1d8b0f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('challenges')}
    if 'default_map_url' not in cols:
        op.add_column('challenges', sa.Column('default_map_url', sa.Text(), nullable=True))

def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('challenges')}
    if 'default_map_url' in cols:
        op.drop_column('challenges', 'default_map_url')