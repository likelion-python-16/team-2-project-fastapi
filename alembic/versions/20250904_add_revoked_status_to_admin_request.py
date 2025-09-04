"""add revoked status to admin request

Revision ID: 20250904_add_revoked
Revises: 20250903_add_admin_audit_logs
Create Date: 2025-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250904_add_revoked'
down_revision = '20250903_add_admin_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'revoked' to AdminRequest.status across dialects
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # Postgres named enum type
        op.execute("ALTER TYPE admin_request_status ADD VALUE IF NOT EXISTS 'revoked'")
    elif dialect in ('mysql', 'mariadb'):
        # MySQL/MariaDB: 일부 드라이버에서 alter_column이 enum default 변경을 제대로 반영하지 못할 수 있음
        # 1) NULL 값 보정
        op.execute("UPDATE admin_requests SET status='pending' WHERE status IS NULL")
        # 2) 컬럼 ENUM 정의 + NOT NULL + DEFAULT 'pending' 으로 재정의
        op.execute(
            "ALTER TABLE admin_requests "
            "MODIFY COLUMN status ENUM('pending','approved','rejected','revoked') "
            "NOT NULL DEFAULT 'pending'"
        )
    else:
        # SQLite or others (Enum usually stored as VARCHAR). No-op is fine,
        # but we still run an alter to keep Alembic history consistent.
        try:
            op.alter_column(
                'admin_requests',
                'status',
                existing_type=sa.String(length=20),
                type_=sa.String(length=20),
                existing_nullable=False,
                nullable=False,
            )
        except Exception:
            pass


def downgrade():
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type
    # For now, we'll leave a comment that this is not easily reversible
    pass
