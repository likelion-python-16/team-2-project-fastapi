"""add default_place_id to challenges

Revision ID: add_challenge_default_place_id
Revises: add_challenge_cover_image
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_challenge_default_place_id'
down_revision = 'add_challenge_cover_image'
branch_labels = None
depends_on = None
def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols
def upgrade() -> None:
    if not _has_column('challenges', 'default_place_id'):
        with op.batch_alter_table('challenges') as batch:
            batch.add_column(sa.Column('default_place_id', sa.String(length=64), nullable=True))
def downgrade() -> None:
    if _has_column('challenges', 'default_place_id'):
        with op.batch_alter_table('challenges') as batch:
            batch.drop_column('default_place_id')
