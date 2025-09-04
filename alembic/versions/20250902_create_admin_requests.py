"""create admin_requests table

Revision ID: 20250902_create_admin_requests
Revises: 20250902_add_is_admin
Create Date: 2025-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20250902_create_admin_requests"
down_revision: Union[str, Sequence[str], None] = "20250902_add_is_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM 타입 이름은 글로벌 스키마 네임스페이스에 등록되므로 중복 주의.
    status_enum = sa.Enum("pending", "approved", "rejected", name="admin_request_status")

    op.create_table(
        "admin_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )

    # 인덱스는 별도로 생성
    op.create_index("ix_admin_requests_user_id", "admin_requests", ["user_id"])
    op.create_index("ix_admin_requests_reviewed_by", "admin_requests", ["reviewed_by"])
    op.create_index("ix_admin_requests_status", "admin_requests", ["status"])


def downgrade() -> None:
    # 인덱스부터 제거
    try:
        op.drop_index("ix_admin_requests_status", table_name="admin_requests")
    except Exception:
        pass
    try:
        op.drop_index("ix_admin_requests_reviewed_by", table_name="admin_requests")
    except Exception:
        pass
    try:
        op.drop_index("ix_admin_requests_user_id", table_name="admin_requests")
    except Exception:
        pass

    # 테이블 제거
    try:
        op.drop_table("admin_requests")
    except Exception:
        pass

    # (MySQL은 ENUM 타입을 별도 드롭할 필요가 보통 없음. Postgres라면 op.execute("DROP TYPE admin_request_status") 필요)
