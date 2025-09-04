"""post-fix: email_verifications tweaks

Revision ID: 828d181a4bb4
Revises: db1cb18105bb
Create Date: 2025-08-27 18:50:47.247262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '828d181a4bb4'
down_revision: Union[str, Sequence[str], None] = 'db1cb18105bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
