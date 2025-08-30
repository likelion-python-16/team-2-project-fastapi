"""
Add reward fields to challenge_rounds

Revision ID: 20250829_add_round_reward_fields
Revises: 7d272d2afd60_merge_heads_cover_image_default_place_id
Create Date: 2025-08-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250829_add_round_reward_fields'
down_revision = '7d272d2afd60'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('challenge_rounds') as batch:
        batch.add_column(sa.Column('reward_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch.add_column(sa.Column('reward_text', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('challenge_rounds') as batch:
        batch.drop_column('reward_text')
        batch.drop_column('reward_enabled')

