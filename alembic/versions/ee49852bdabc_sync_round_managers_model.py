from alembic import op
import sqlalchemy as sa

revision = "ee49852bdabc"
down_revision = "1027059025e0"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 현재 상태 조회
    cols = {c["name"] for c in insp.get_columns("round_managers")}
    idxs = {i["name"] for i in insp.get_indexes("round_managers")}
    uqs  = {u["name"] for u in insp.get_unique_constraints("round_managers")}

    # 1) updated_at 컬럼이 없으면 추가
    if "updated_at" not in cols:
        op.add_column(
            "round_managers",
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False)
        )

    # 2) 유니크 제약(라운드당 1명) 없으면 추가
    #    MySQL에서는 unique가 인덱스로 잡힐 수 있으니 둘 다 확인
    if "uq_round_manager_one_per_round" not in uqs and "uq_round_manager_one_per_round" not in idxs:
        op.create_unique_constraint(
            "uq_round_manager_one_per_round",
            "round_managers",
            ["challenge_id", "round_id"]
        )

    # 3) 필요한 인덱스가 없으면 추가 (기존 단일컬럼 인덱스들은 FK 때문에 그대로 둠)
    if "ix_rm_ch_round" not in idxs:
        op.create_index("ix_rm_ch_round", "round_managers", ["challenge_id", "round_id"])
    if "ix_rm_user" not in idxs:
        op.create_index("ix_rm_user", "round_managers", ["user_id"])


def downgrade():
    # 우리가 추가한 것만 안전하게 제거 (있을 때만)
    bind = op.get_bind()
    insp = sa.inspect(bind)

    idxs = {i["name"] for i in insp.get_indexes("round_managers")}
    uqs  = {u["name"] for u in insp.get_unique_constraints("round_managers")}
    cols = {c["name"] for c in insp.get_columns("round_managers")}

    if "ix_rm_user" in idxs:
        op.drop_index("ix_rm_user", table_name="round_managers")
    if "ix_rm_ch_round" in idxs:
        op.drop_index("ix_rm_ch_round", table_name="round_managers")
    if "uq_round_manager_one_per_round" in uqs:
        op.drop_constraint("uq_round_manager_one_per_round", "round_managers", type_="unique")
    if "updated_at" in cols:
        op.drop_column("round_managers", "updated_at")
