"""add reward_description/use_reward to challenges if missing (with backfill)

Revision ID: 8e2a3c1d8b0d
Revises: 8e2a3c1d8b0c
Create Date: 2025-09-05 01:28:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '8e2a3c1d8b0d'
down_revision = '8e2a3c1d8b0c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('challenges')}

    # Add use_reward if missing
    if 'use_reward' not in cols:
        op.add_column('challenges', sa.Column('use_reward', sa.Boolean(), nullable=False, server_default='0'))
        op.alter_column('challenges', 'use_reward', server_default=None)

    # Add reward_description if missing
    if 'reward_description' not in cols:
        op.add_column('challenges', sa.Column('reward_description', sa.Text(), nullable=True))

        # Backfill from legacy 'reward' if exists
        cols = {c['name'] for c in insp.get_columns('challenges')}
        if 'reward' in cols:
            op.execute(text("UPDATE challenges SET reward_description = COALESCE(reward, reward_description)"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('challenges')}
    if 'reward_description' in cols:
        op.drop_column('challenges', 'reward_description')
    if 'use_reward' in cols:
        op.drop_column('challenges', 'use_reward')

