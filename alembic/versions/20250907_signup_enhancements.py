"""Signup/Admin users enhancements (idempotent)

Revision ID: 20250907_signup_enhancements
Revises: 20250904_chat_dm_nullable
Create Date: 2025-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250907_signup_enhancements"
down_revision: Union[str, Sequence[str], None] = "20250904_chat_dm_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def _has_unique(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(uc["name"] == name for uc in insp.get_unique_constraints(table))


def upgrade() -> None:
    # --- Users basic flags ---
    if not _has_column("users", "is_superadmin"):
        op.add_column("users", sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default="0"))
        op.alter_column("users", "is_superadmin", server_default=None)

    if not _has_column("users", "is_deleted"):
        op.add_column("users", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        op.alter_column("users", "is_deleted", server_default=None)
    if not _has_index("users", "ix_users_is_deleted"):
        op.create_index("ix_users_is_deleted", "users", ["is_deleted"], unique=False)

    if not _has_column("users", "deleted_at"):
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # --- Activation/verification flags ---
    if not _has_column("users", "is_active"):
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="0"))
        op.alter_column("users", "is_active", server_default=None)

    if not _has_column("users", "email_verified"):
        op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="0"))
        op.alter_column("users", "email_verified", server_default=None)

    # --- Token version ---
    if not _has_column("users", "token_version"):
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
        op.alter_column("users", "token_version", server_default=None)

    # --- Social identity uniqueness ---
    # Ensure unique(provider, provider_id) if both columns exist
    if _has_column("users", "provider") and _has_column("users", "provider_id"):
        if not _has_unique("users", "uq_user_provider_pid"):
            op.create_unique_constraint("uq_user_provider_pid", "users", ["provider", "provider_id"])

    # --- Phone & identification secure fields ---
    if not _has_column("users", "phone_encrypted"):
        op.add_column("users", sa.Column("phone_encrypted", sa.String(length=255), nullable=True))
    if not _has_column("users", "phone_fingerprint"):
        op.add_column("users", sa.Column("phone_fingerprint", sa.String(length=64), nullable=True))
        # unique index name consistent
        if not _has_index("users", "ix_users_phone_fingerprint"):
            op.create_index("ix_users_phone_fingerprint", "users", ["phone_fingerprint"], unique=True)

    if not _has_column("users", "identification_number"):
        op.add_column("users", sa.Column("identification_number", sa.String(length=255), nullable=True))
    if not _has_column("users", "identification_fingerprint"):
        op.add_column("users", sa.Column("identification_fingerprint", sa.String(length=64), nullable=True))
        if not _has_index("users", "ix_users_identification_fingerprint"):
            op.create_index(
                "ix_users_identification_fingerprint", "users", ["identification_fingerprint"], unique=True
            )

    # --- Gender enum & column ---
    if not _has_column("users", "gender"):
        gender_enum = sa.Enum("male", "female", "other", name="gender_enum")
        op.add_column("users", sa.Column("gender", gender_enum, nullable=False, server_default="other"))
        op.alter_column("users", "gender", server_default=None)

    # --- Birth year (already present in prior migration in many envs) ---
    if not _has_column("users", "birth_year"):
        op.add_column("users", sa.Column("birth_year", sa.String(length=10), nullable=True))

    # --- Profile & introduction safety ---
    # profile_image should be NOT NULL with default '' in application; we keep nullable to avoid wide locks;
    # at least ensure column exists (it does) and backfill introduction to '' then set NOT NULL.
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET introduction = '' WHERE introduction IS NULL"))
    try:
        op.alter_column("users", "introduction", existing_type=sa.Text(), nullable=False)
    except Exception:
        # some engines may already be NOT NULL or type differs; skip
        pass

    # region_active often filtered; index helps
    if _has_column("users", "region_active") and not _has_index("users", "ix_users_region_active"):
        op.create_index("ix_users_region_active", "users", ["region_active"], unique=False)


def downgrade() -> None:
    # be conservative: drop only constraints and indexes created here
    if _has_unique("users", "uq_user_provider_pid"):
        op.drop_constraint("uq_user_provider_pid", "users", type_="unique")
    if _has_index("users", "ix_users_is_deleted"):
        op.drop_index("ix_users_is_deleted", table_name="users")
    if _has_index("users", "ix_users_phone_fingerprint"):
        op.drop_index("ix_users_phone_fingerprint", table_name="users")
    if _has_index("users", "ix_users_identification_fingerprint"):
        op.drop_index("ix_users_identification_fingerprint", table_name="users")
    if _has_index("users", "ix_users_region_active"):
        op.drop_index("ix_users_region_active", table_name="users")

