"""Ensure email_verifications has required columns & indexes (idempotent)

Revision ID: 20250908_fix_email_verifications_table
Revises: 20250908_readd_cover_image_url
Create Date: 2025-09-08 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2e1f0c8b901"
down_revision: Union[str, Sequence[str], None] = "20250908_readd_cover_image_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    # Ensure table exists
    if not _has_table("email_verifications"):
        op.create_table(
            "email_verifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token", sa.String(length=128), nullable=False),
            sa.Column("sent_to", sa.String(length=120), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="email_verifications_ibfk_1", ondelete="CASCADE"),
        )

    # Add missing columns idempotently
    for col, type_, nullable, default in [
        ("token", sa.String(length=128), False, None),
        ("sent_to", sa.String(length=120), False, None),
        ("expires_at", sa.DateTime(), False, None),
        ("used_at", sa.DateTime(), True, None),
        ("created_at", sa.DateTime(), False, sa.text("CURRENT_TIMESTAMP")),
    ]:
        if not _has_column("email_verifications", col):
            if default is not None:
                op.add_column("email_verifications", sa.Column(col, type_, nullable=nullable, server_default=default))
            else:
                op.add_column("email_verifications", sa.Column(col, type_, nullable=nullable))

    # Indexes / unique
    if not _has_index("email_verifications", "ix_email_verifications_user_id"):
        op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"], unique=False)
    # MySQL auto-creates an index for UNIQUE; ensure a unique index on token
    bind = op.get_bind()
    # check if a unique index or constraint named 'uq_email_verifications_token' or similar exists
    # fall back to creating an index and unique constraint by name
    if not _has_index("email_verifications", "ix_email_verifications_token"):
        op.create_index("ix_email_verifications_token", "email_verifications", ["token"], unique=True)


def downgrade() -> None:
    # Keep downgrade safe: do not drop table; only drop indexes we added
    if _has_index("email_verifications", "ix_email_verifications_token"):
        op.drop_index("ix_email_verifications_token", table_name="email_verifications")
    if _has_index("email_verifications", "ix_email_verifications_user_id"):
        op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
