"""Make chat_rooms.challenge_id nullable for DM rooms

Revision ID: 20250904_chat_dm_nullable
Revises: f23a5f6f4167
Create Date: 2025-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250904_chat_dm_nullable'
down_revision: Union[str, Sequence[str], None] = 'f23a5f6f4167'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'chat_rooms',
        'challenge_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'chat_rooms',
        'challenge_id',
        existing_type=sa.Integer(),
        nullable=False,
    )

