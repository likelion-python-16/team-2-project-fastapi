"""challenge: add updated_at, switch status to ENUM, add cover fields

Revision ID: 3682c019c3fa
Revises: 7cc008d3ced4
Create Date: 2025-09-01 23:27:40.158367
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "3682c019c3fa"
down_revision: Union[str, Sequence[str], None] = "7cc008d3ced4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) updated_at 추가 (임시 default now())
    op.add_column(
        "challenges",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    #   └ MySQL에서 ON UPDATE CURRENT_TIMESTAMP 보장 (Alembic 표현 미흡 → RAW SQL로 보정)
    op.execute(
        """
        ALTER TABLE challenges
        MODIFY COLUMN updated_at DATETIME
        NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
        """
    )

    # 2) status 사전정리(혹시 모를 NULL/빈값)
    op.execute("UPDATE challenges SET status='recruiting' WHERE status IS NULL OR status=''")

    # 3) status: VARCHAR(20) → ENUM + NOT NULL + DEFAULT 'recruiting'
    op.alter_column(
        "challenges",
        "status",
        existing_type=mysql.VARCHAR(length=20),
        type_=sa.Enum("recruiting", "active", "completed", "cancelled", name="challenge_status_enum"),
        existing_nullable=True,                 # 자동생성본 힌트 값, 실상태와 무관
        nullable=False,                         # 확실히 NOT NULL
        existing_comment="챌린지 상태",
        server_default=sa.text("'recruiting'"), # 기본값 보장
    )


def downgrade() -> None:
    # status: ENUM → VARCHAR(20) (NOT NULL + DEFAULT 유지)
    op.alter_column(
        "challenges",
        "status",
        existing_type=sa.Enum("recruiting", "active", "completed", "cancelled", name="challenge_status_enum"),
        type_=mysql.VARCHAR(length=20),
        nullable=False,                          # ← nullable=True 였던 자동본을 수정
        existing_comment="챌린지 상태",
        server_default=sa.text("'recruiting'"),
    )

    # updated_at 제거
    op.drop_column("challenges", "updated_at")
