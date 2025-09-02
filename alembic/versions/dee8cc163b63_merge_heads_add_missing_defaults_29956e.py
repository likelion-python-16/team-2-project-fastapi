"""merge heads: add_missing_defaults + 29956e

Revision ID: dee8cc163b63
Revises: 20250902_add_missing_challenge_defaults, 29956e138298
Create Date: 2025-09-01 23:00:16.134571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dee8cc163b63'
down_revision: Union[str, Sequence[str], None] = ('20250902_add_missing_challenge_defaults', '29956e138298')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
