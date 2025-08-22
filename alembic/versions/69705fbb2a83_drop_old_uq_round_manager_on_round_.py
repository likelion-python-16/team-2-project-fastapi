from alembic import op
import sqlalchemy as sa

revision = "69705fbb2a83"
down_revision = "ee49852bdabc"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    uqs = {u["name"] for u in insp.get_unique_constraints("round_managers")}
    # 불필요한 유니크만 제거: (round_id, user_id)
    if "uq_round_manager" in uqs:
        op.drop_constraint("uq_round_manager", "round_managers", type_="unique")

def downgrade():
    # 되돌릴 때는 이전 유니크 복원
    op.create_unique_constraint(
        "uq_round_manager",
        "round_managers",
        ["round_id", "user_id"]
    )
