"""challenge: status enum + add updated_at

Revision ID: 7cc008d3ced4
Revises: b53dd17c0d32
Create Date: 2025-09-01 23:24:04.527559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cc008d3ced4'
down_revision: Union[str, Sequence[str], None] = 'b53dd17c0d32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
