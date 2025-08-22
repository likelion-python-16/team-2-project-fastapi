from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1027059025e0"
down_revision: Union[str, Sequence[str], None] = "93404b02e063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()

def upgrade() -> None:
    # round_managers 테이블이 이미 있으면 생성 스킵
    if not _has_table("round_managers"):
        op.create_table(
            "round_managers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("challenge_id", sa.Integer(), nullable=False),
            sa.Column("round_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("challenge_id", "round_id", name="uq_round_manager_one_per_round"),
            sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["round_id"], ["challenge_rounds.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )

def downgrade() -> None:
    # 안전하게 있을 때만 제거
    if _has_table("round_managers"):
        op.drop_table("round_managers")
