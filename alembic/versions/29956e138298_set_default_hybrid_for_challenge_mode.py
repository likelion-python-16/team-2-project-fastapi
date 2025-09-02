"""set default hybrid for challenge.mode

Revision ID: 29956e138298
Revises: 20250902_fix_challenge_status_enum
Create Date: 2025-09-01 22:03:21.443806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29956e138298'
down_revision: Union[str, Sequence[str], None] = '20250902_fix_challenge_status_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        # 혹시 모를 NULL 값 방지 (이전 상태가 NULL 허용이었다면)
        op.execute("UPDATE challenges SET mode='hybrid' WHERE mode IS NULL")
        # ENUM 멤버 그대로 유지하면서 기본값만 부여 + NOT NULL 유지
        op.execute(
            """
            ALTER TABLE challenges
            MODIFY COLUMN mode ENUM('online','offline','hybrid')
            NOT NULL DEFAULT 'hybrid'
            """
        )
    else:
        # 기타 DB: 문자열로 변경/유지하며 기본값+NOT NULL 적용 (보수적)
        op.alter_column(
            "challenges",
            "mode",
            existing_type=sa.String(length=10),
            server_default="hybrid",
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        # 기본값만 제거하고 NOT NULL은 유지 (이전 상태가 그랬음)
        op.execute(
            """
            ALTER TABLE challenges
            MODIFY COLUMN mode ENUM('online','offline','hybrid')
            NOT NULL
            """
        )
    else:
        op.alter_column(
            "challenges",
            "mode",
            existing_type=sa.String(length=10),
            server_default=None,
            nullable=False,
        )