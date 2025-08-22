"""add phone_encrypted & phone_fingerprint to users

Revision ID: d0c0e356a69b
Revises: 28cebf81243d
Create Date: 2025-08-18 03:37:11.548785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0c0e356a69b'
down_revision: Union[str, Sequence[str], None] = '28cebf81243d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("users", "phone_encrypted"):
        op.add_column("users", sa.Column("phone_encrypted", sa.String(length=255), nullable=True))
    if not _has_column("users", "phone_fingerprint"):
        op.add_column("users", sa.Column("phone_fingerprint", sa.String(length=255), nullable=True))

def downgrade() -> None:
    if _has_column("users", "phone_fingerprint"):
        op.drop_column("users", "phone_fingerprint")
    if _has_column("users", "phone_encrypted"):
        op.drop_column("users", "phone_encrypted")
