"""AdminRequest: add 'revoked' to status enum and index user_id (idempotent)

Revision ID: 20250907_admin_request_revoked
Revises: 20250907_add_default_map_url
Create Date: 2025-09-07 00:00:20.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20250907_admin_request_revoked"
down_revision: Union[str, Sequence[str], None] = "20250907_add_default_map_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name.lower()

    # Ensure 'revoked' exists in admin_request_status enum (MySQL path)
    if dialect in ("mysql", "mariadb"):
        res = bind.execute(sa.text(
            """
            SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME='admin_requests' AND COLUMN_NAME='status'
            """
        )).fetchone()
        if res:
            coltype = str(res[0])
            if "revoked" not in coltype:
                # Replace enum set with new one
                op.execute(
                    "ALTER TABLE admin_requests "
                    "MODIFY COLUMN status ENUM('pending','approved','rejected','revoked') NOT NULL DEFAULT 'pending'"
                )
    else:
        # Generic fallback: recreate enum using type-alter (may be no-op on some engines)
        try:
            new_enum = sa.Enum('pending','approved','rejected','revoked', name='admin_request_status')
            op.alter_column('admin_requests', 'status', type_=new_enum, existing_nullable=False, existing_server_default=sa.text("'pending'"))
        except Exception:
            pass

    # Ensure index on user_id exists
    if not _has_index('admin_requests', 'ix_admin_requests_user_id'):
        op.create_index('ix_admin_requests_user_id', 'admin_requests', ['user_id'], unique=False)


def downgrade() -> None:
    # drop index only; keep enum change to avoid data loss
    if _has_index('admin_requests', 'ix_admin_requests_user_id'):
        op.drop_index('ix_admin_requests_user_id', table_name='admin_requests')

