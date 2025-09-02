"""
cascade email_verifications.user_id and soft delete fields on users

Revision ID: 20250901_cascade_ev_and_soft_delete_users
Revises: 20250830_add_social_login_fields
Create Date: 2025-09-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20250901_cascade_ev_and_soft_delete_users"
down_revision = "20250830_add_social_login_fields"
branch_labels = None
depends_on = None


# ---------- helpers (멱등 체크) ----------
def _insp():
    return inspect(op.get_bind())

def _has_column(table: str, col: str) -> bool:
    return any(c["name"] == col for c in _insp().get_columns(table))

def _has_index(table: str, ix_name: str) -> bool:
    return any(ix["name"] == ix_name for ix in _insp().get_indexes(table))

def _find_fk_email_verifications_user_id():
    """email_verifications.user_id -> users(id) FK 정보 반환 (없으면 None)"""
    for fk in _insp().get_foreign_keys("email_verifications"):
        if fk.get("referred_table") == "users" and fk.get("constrained_columns") == ["user_id"]:
            return fk
    return None

def _fk_is_cascade(fk_dict) -> bool:
    # SQLAlchemy 1.4/2.x에서 MySQL의 ondelete는 fk_dict.get("options", {}).get("ondelete")
    # 또는 fk_dict.get("ondelete") 로 노출될 수 있어 방어적으로 확인
    return (
        (fk_dict.get("options") or {}).get("ondelete", "").upper() == "CASCADE"
        or str(fk_dict.get("ondelete", "")).upper() == "CASCADE"
    )


def upgrade() -> None:
    # 1) users: soft-delete 컬럼/인덱스 (존재하면 건너뛰기)
    with op.batch_alter_table("users") as batch:
        if not _has_column("users", "is_deleted"):
            batch.add_column(
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0"))
            )
        if not _has_column("users", "deleted_at"):
            batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        if not _has_index("users", "ix_users_is_deleted"):
            batch.create_index("ix_users_is_deleted", ["is_deleted"])

    # 2) email_verifications.user_id -> users(id) FK 를 ON DELETE CASCADE 로 정규화
    current_fk = _find_fk_email_verifications_user_id()
    if current_fk:
        # 이미 CASCADE면 그대로 두고, 아니면 교체
        if not _fk_is_cascade(current_fk):
            op.drop_constraint(current_fk["name"], "email_verifications", type_="foreignkey")
            op.create_foreign_key(
                "fk_email_verifications_user_id_users_cascade",
                "email_verifications",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )
    else:
        # FK가 없으면 새로 생성
        op.create_foreign_key(
            "fk_email_verifications_user_id_users_cascade",
            "email_verifications",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # 1) FK를 "on delete 없음" 상태로 되돌림 (있을 때만)
    current_fk = _find_fk_email_verifications_user_id()
    if current_fk:
        op.drop_constraint(current_fk["name"], "email_verifications", type_="foreignkey")
        op.create_foreign_key(
            "fk_email_verifications_user_id_users",
            "email_verifications",
            "users",
            ["user_id"],
            ["id"],
        )

    # 2) users: soft-delete 인덱스/컬럼 제거 (있을 때만)
    with op.batch_alter_table("users") as batch:
        if _has_index("users", "ix_users_is_deleted"):
            batch.drop_index("ix_users_is_deleted")
        if _has_column("users", "deleted_at"):
            batch.drop_column("deleted_at")
        if _has_column("users", "is_deleted"):
            batch.drop_column("is_deleted")
