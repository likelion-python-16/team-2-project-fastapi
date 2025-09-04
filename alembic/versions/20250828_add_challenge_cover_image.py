"""add cover image fields to challenges

Revision ID: add_challenge_cover_image
Revises: 
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_challenge_cover_image'
down_revision = "3d214f10a283"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('challenges') as batch:
        batch.add_column(sa.Column('cover_image_url', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('cover_round_picture_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_challenge_cover_round_picture',
        source_table='challenges',
        referent_table='round_pictures',
        local_cols=['cover_round_picture_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_challenge_cover_round_picture', 'challenges', type_='foreignkey')
    with op.batch_alter_table('challenges') as batch:
        batch.drop_column('cover_round_picture_id')
        batch.drop_column('cover_image_url')

