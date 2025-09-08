"""merge_multiple_heads

Revision ID: 724acfd982f4
Revises: 20250907_admin_request_revoked, 6ed3739a3a89, social_login_fields
Create Date: 2025-09-08 13:37:13.164015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '724acfd982f4'
down_revision: Union[str, Sequence[str], None] = ('20250907_admin_request_revoked', '6ed3739a3a89', 'social_login_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
