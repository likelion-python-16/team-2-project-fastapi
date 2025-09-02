"""fix created_at default on challenges

Revision ID: 53c5afebc3ab
Revises: 3682c019c3fa
Create Date: 2025-09-01 23:36:20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# --- REQUIRED Alembic metadata ---
revision: str = "53c5afebc3ab"
down_revision: Union[str, Sequence[str], None] = "3682c019c3fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 기존 NULL → NOW() (NOT NULL 변경 전 안전처리)
    op.execute("UPDATE challenges SET created_at = NOW() WHERE created_at IS NULL")
    # NOT NULL + DEFAULT CURRENT_TIMESTAMP
    op.alter_column(
        "challenges",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

def downgrade() -> None:
    # DEFAULT 제거 + NULL 허용
    op.alter_column(
        "challenges",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None,
    )
