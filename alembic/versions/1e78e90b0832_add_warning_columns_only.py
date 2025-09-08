"""Add warning columns only

Revision ID: 1e78e90b0832
Revises: 67c0098138eb
Create Date: 2025-09-05 04:11:44.734138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e78e90b0832'
down_revision: Union[str, Sequence[str], None] = 'manner_score_30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add warning system columns."""
    # Add warning_count and is_review_banned columns
    op.add_column('users', sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('is_review_banned', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Remove warning system columns."""
    op.drop_column('users', 'is_review_banned')
    op.drop_column('users', 'warning_count')
