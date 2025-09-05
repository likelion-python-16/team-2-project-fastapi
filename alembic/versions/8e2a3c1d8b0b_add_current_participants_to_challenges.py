"""add current_participants to challenges if missing

Revision ID: 8e2a3c1d8b0b
Revises: 8e2a3c1d8b0a
Create Date: 2025-09-05 01:12:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '8e2a3c1d8b0b'
down_revision = '8e2a3c1d8b0a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('challenges')}

    if 'current_participants' not in cols:
        op.add_column('challenges', sa.Column('current_participants', sa.Integer(), nullable=False, server_default='0'))
        # Drop server default to keep behavior consistent with application-level defaults
        op.alter_column('challenges', 'current_participants', server_default=None)

    # Ensure composite index exists (current_participants, max_participants)
    idx_names = {ix['name'] for ix in insp.get_indexes('challenges')}
    if 'ix_challenge_participants' not in idx_names:
        op.create_index('ix_challenge_participants', 'challenges', ['current_participants', 'max_participants'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = {ix['name'] for ix in insp.get_indexes('challenges')}
    if 'ix_challenge_participants' in idx_names:
        op.drop_index('ix_challenge_participants', table_name='challenges')
    cols = {c['name'] for c in insp.get_columns('challenges')}
    if 'current_participants' in cols:
        op.drop_column('challenges', 'current_participants')

