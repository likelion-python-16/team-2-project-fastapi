"""Add missing default place/map fields to challenges

Revision ID: 20250902_add_missing_challenge_defaults
Revises: 29956e138298
Create Date: 2025-09-02 00:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250902_add_missing_challenge_defaults'
down_revision: Union[str, Sequence[str], None] = "20250901_cascade_ev_and_soft_delete_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    # Add columns if they don't exist
    with op.batch_alter_table('challenges') as batch:
        if not _has_column('challenges', 'same_place_for_all_rounds'):
            batch.add_column(sa.Column('same_place_for_all_rounds', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        if not _has_column('challenges', 'default_map_url'):
            batch.add_column(sa.Column('default_map_url', sa.String(length=512), nullable=True))
        if not _has_column('challenges', 'default_latitude'):
            batch.add_column(sa.Column('default_latitude', sa.Float(), nullable=True))
        if not _has_column('challenges', 'default_longitude'):
            batch.add_column(sa.Column('default_longitude', sa.Float(), nullable=True))

    # Normalize server_default to literal False after creation
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TABLE challenges ALTER COLUMN same_place_for_all_rounds SET DEFAULT FALSE")
    elif bind.dialect.name == 'mysql':
        op.execute("ALTER TABLE challenges ALTER COLUMN same_place_for_all_rounds SET DEFAULT 0")


def downgrade() -> None:
    with op.batch_alter_table('challenges') as batch:
        if _has_column('challenges', 'default_longitude'):
            batch.drop_column('default_longitude')
        if _has_column('challenges', 'default_latitude'):
            batch.drop_column('default_latitude')
        if _has_column('challenges', 'default_map_url'):
            batch.drop_column('default_map_url')
        if _has_column('challenges', 'same_place_for_all_rounds'):
            batch.drop_column('same_place_for_all_rounds')

