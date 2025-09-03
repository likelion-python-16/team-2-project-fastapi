"""merge heads after admin changes

Revision ID: 0bb9a42874c9
Revises: 20250902_add_is_superadmin_to_users, 20250902_drop_admin_users, 53c5afebc3ab
Create Date: 2025-09-02 20:42:35.206506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bb9a42874c9'
down_revision: Union[str, Sequence[str], None] = ('20250902_add_is_superadmin_to_users', '20250902_drop_admin_users', '53c5afebc3ab')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
