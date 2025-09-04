"""fix default pending on admin_requests

Revision ID: e4fc9c3a683d
Revises: 20250904_add_revoked
Create Date: 2025-09-03 20:46:26.861964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4fc9c3a683d'
down_revision: Union[str, Sequence[str], None] = '20250904_add_revoked'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("UPDATE admin_requests SET status='pending' WHERE status IS NULL")
    op.execute(
        "ALTER TABLE admin_requests "
        "MODIFY COLUMN status ENUM('pending','approved','rejected','revoked') "
        "NOT NULL DEFAULT 'pending'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
