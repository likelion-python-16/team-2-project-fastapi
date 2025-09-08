"""fix NULLs & add is_superadmin

Revision ID: fc7b0d47abe9
Revises: c95bf5c693e9
Create Date: 2025-09-08 14:27:45.627456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc7b0d47abe9'
down_revision: Union[str, Sequence[str], None] = 'c95bf5c693e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
