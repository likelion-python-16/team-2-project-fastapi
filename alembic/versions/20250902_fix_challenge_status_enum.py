"""Normalize challenges.status to support 'recruiting' (and others)

Revision ID: 20250902_fix_challenge_status_enum
Revises: 7d272d2afd60
Create Date: 2025-09-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250902_fix_challenge_status_enum'
down_revision: Union[str, Sequence[str], None] = "20250901_cascade_ev_and_soft_delete_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Target allowed statuses used by the app
    allowed = ["recruiting", "active", "completed", "cancelled"]

    if dialect == 'mysql':
        # If status is an ENUM but missing values, convert/normalize
        # MySQL allows MODIFY to reset enum members and default
        op.execute(
            """
            ALTER TABLE challenges
            MODIFY COLUMN status ENUM('recruiting','active','completed','cancelled')
            DEFAULT 'recruiting'
            COMMENT '챌린지 상태'
            """
        )
        # Also normalize mode enum to include 'hybrid'
        op.execute(
            """
            ALTER TABLE challenges
            MODIFY COLUMN mode ENUM('online','offline','hybrid') NOT NULL
            """
        )
    elif dialect == 'postgresql':
        # On Postgres, safest path is to convert to VARCHAR(20)
        # (keeps compatibility with app which treats it as string)
        op.alter_column(
            'challenges', 'status',
            type_=sa.String(length=20),
            existing_nullable=True,
            existing_comment='챌린지 상태',
        )
    else:
        # Generic fallback
        op.alter_column(
            'challenges', 'status',
            type_=sa.String(length=20),
            existing_nullable=True,
            existing_comment='챌린지 상태',
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'mysql':
        # Revert to a permissive VARCHAR to avoid data loss
        op.alter_column(
            'challenges', 'status',
            type_=sa.String(length=20),
            existing_nullable=True,
            existing_comment='챌린지 상태',
        )
    elif dialect == 'postgresql':
        # No-op safe downgrade (remain as VARCHAR)
        pass
    else:
        pass
