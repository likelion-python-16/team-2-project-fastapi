"""add phone_encrypted & phone_fingerprint to users

Revision ID: d0c0e356a69b
Revises: 28cebf81243d
Create Date: 2025-08-18 03:37:11.548785
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d0c0e356a69b"
down_revision: Union[str, Sequence[str], None] = "28cebf81243d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return insp.has_table(table)


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not _has_table(table):
        return False
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
        return column in cols
    except Exception as e:
        # 리플렉션 실패 시, 없는 것으로 간주하여 안전하게 진행
        print(f"[alembic] warning: get_columns failed for {table}: {e}")
        return False


def upgrade() -> None:
    if not _has_table("users"):
        print("[alembic] users table not found; skipping this migration.")
        return

    with op.batch_alter_table("users") as batch:
        if not _has_column("users", "phone_encrypted"):
            batch.add_column(sa.Column("phone_encrypted", sa.String(length=255), nullable=True))
        if not _has_column("users", "phone_fingerprint"):
            # 길이 64 + unique 권장 (해시 지문 가정)
            batch.add_column(sa.Column("phone_fingerprint", sa.String(length=64), nullable=True, unique=True))


def downgrade() -> None:
    if not _has_table("users"):
        return

    with op.batch_alter_table("users") as batch:
        if _has_column("users", "phone_fingerprint"):
            batch.drop_column("phone_fingerprint")
        if _has_column("users", "phone_encrypted"):
            batch.drop_column("phone_encrypted")
