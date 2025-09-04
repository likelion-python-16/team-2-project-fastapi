"""drop admin_users table if exists

Revision ID: 20250902_drop_admin_users
Revises: 20250902_create_admin_requests
Create Date: 2025-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20250902_drop_admin_users"
down_revision: Union[str, Sequence[str], None] = "20250902_create_admin_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL for portability (MySQL/MariaDB, SQLite)
    try:
        op.execute("DROP TABLE IF EXISTS admin_users")
    except Exception:
        pass


def downgrade() -> None:
    # No-op (table intentionally removed). If needed, recreate manually.
    pass
