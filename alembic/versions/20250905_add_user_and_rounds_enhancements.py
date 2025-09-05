"""Add user and challenge_rounds enhancements

Revision ID: 20250905_user_rounds_enh
Revises: f23a5f6f4167
Create Date: 2025-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250905_user_rounds_enh"
down_revision: Union[str, Sequence[str], None] = "f23a5f6f4167"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table_name)}
    return column_name in cols


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = {ix["name"] for ix in insp.get_indexes(table_name)}
    return index_name in indexes


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    uniques = {uc["name"] for uc in insp.get_unique_constraints(table_name)}
    return constraint_name in uniques


def upgrade() -> None:
    # --- users table enhancements ---
    if not _has_column("users", "is_superadmin"):
        op.add_column(
            "users",
            sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default="0"),
        )

    if not _has_column("users", "is_deleted"):
        op.add_column(
            "users",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        )
    # index on users.is_deleted
    if _has_column("users", "is_deleted") and not _has_index("users", "ix_users_is_deleted"):
        op.create_index(
            "ix_users_is_deleted",
            "users",
            ["is_deleted"],
            unique=False,
        )

    if not _has_column("users", "deleted_at"):
        op.add_column(
            "users",
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )

    # Unique constraint on (provider, provider_id)
    # Only add if both columns exist and constraint missing
    if _has_column("users", "provider") and _has_column("users", "provider_id"):
        if not _has_unique_constraint("users", "uq_user_provider_pid"):
            op.create_unique_constraint(
                "uq_user_provider_pid",
                "users",
                ["provider", "provider_id"],
            )

    # --- challenge_rounds table enhancements ---
    if not _has_column("challenge_rounds", "reward_enabled"):
        op.add_column(
            "challenge_rounds",
            sa.Column("reward_enabled", sa.Boolean(), nullable=False, server_default="0"),
        )

    if not _has_column("challenge_rounds", "reward_text"):
        op.add_column(
            "challenge_rounds",
            sa.Column("reward_text", sa.Text(), nullable=True),
        )

    # Index on reward_enabled for quick filtering
    if not _has_index("challenge_rounds", "ix_challenge_rounds_reward_enabled"):
        op.create_index(
            "ix_challenge_rounds_reward_enabled",
            "challenge_rounds",
            ["reward_enabled"],
            unique=False,
        )


def downgrade() -> None:
    # --- challenge_rounds table revert ---
    if _has_index("challenge_rounds", "ix_challenge_rounds_reward_enabled"):
        op.drop_index("ix_challenge_rounds_reward_enabled", table_name="challenge_rounds")

    if _has_column("challenge_rounds", "reward_text"):
        op.drop_column("challenge_rounds", "reward_text")

    if _has_column("challenge_rounds", "reward_enabled"):
        op.drop_column("challenge_rounds", "reward_enabled")

    # --- users table revert ---
    if _has_index("users", "ix_users_is_deleted"):
        op.drop_index("ix_users_is_deleted", table_name="users")
    if _has_unique_constraint("users", "uq_user_provider_pid"):
        op.drop_constraint("uq_user_provider_pid", "users", type_="unique")

    if _has_column("users", "deleted_at"):
        op.drop_column("users", "deleted_at")

    if _has_column("users", "is_deleted"):
        op.drop_column("users", "is_deleted")

    if _has_column("users", "is_superadmin"):
        op.drop_column("users", "is_superadmin")
