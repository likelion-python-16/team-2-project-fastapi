"""add round.zoom_url/reward_* and challenge.default_road_address

Revision ID: a7f2d9c8b3a1
Revises: 40896b14a8dd
Create Date: 2025-09-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a7f2d9c8b3a1"
down_revision: Union[str, None] = "40896b14a8dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Challenges: add default_road_address
    op.add_column('challenges', sa.Column('default_road_address', sa.String(length=300), nullable=True))

    # Challenge rounds: add zoom_url, reward_points, reward_note
    op.add_column('challenge_rounds', sa.Column('zoom_url', sa.Text(), nullable=True))
    op.add_column('challenge_rounds', sa.Column('reward_points', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('challenge_rounds', sa.Column('reward_note', sa.Text(), nullable=True))

    # optional: drop server_default after data migration for reward_points
    with op.batch_alter_table('challenge_rounds') as batch_op:
        batch_op.alter_column('reward_points', server_default=None)


def downgrade() -> None:
    # Challenge rounds: drop columns
    op.drop_column('challenge_rounds', 'reward_note')
    op.drop_column('challenge_rounds', 'reward_points')
    op.drop_column('challenge_rounds', 'zoom_url')

    # Challenges: drop default_road_address
    op.drop_column('challenges', 'default_road_address')

