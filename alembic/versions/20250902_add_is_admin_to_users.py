"""add is_admin to users

Revision ID: 20250902_add_is_admin
Revises: 53c5afebc3ab
Create Date: 2025-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20250902_add_is_admin"
down_revision: Union[str, Sequence[str], None] = '20250901_cascade_ev_and_soft_delete_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 컬럼 추가 (기본값 0)
    try:
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    except Exception:
        # 이미 존재하는 환경 대비
        pass

    # NULL 정리(혹시 모를 환경)
    try:
        op.execute("UPDATE users SET is_admin = 0 WHERE is_admin IS NULL")
    except Exception:
        pass

    # 필요 시: 앞으로 생성되는 레코드 기본값을 유지하려면 그대로 두고,
    # 기본값을 없애려면 아래 주석 해제 (보통은 유지 추천)
    # op.alter_column("users", "is_admin", server_default=None)


def downgrade() -> None:
    try:
        op.drop_column("users", "is_admin")
    except Exception:
        pass
