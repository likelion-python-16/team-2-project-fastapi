from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "93404b02e063"
down_revision: Union[str, Sequence[str], None] = "9942e89fde9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols

def upgrade() -> None:
    # 이 리비전에서 추가하려던 컬럼들을 "있으면 건너뛰기"로 방어
    if not _has_column("challenge_rounds", "address"):
        op.add_column(
            "challenge_rounds",
            sa.Column("address", sa.String(length=255), nullable=True, comment="지번 주소"),
        )

    # (이 파일 안에 다른 add_column 들이 있으면 동일 패턴으로 감싸 주세요)
    # 예)
    # if not _has_column("challenge_rounds", "some_col"):
    #     op.add_column("challenge_rounds", sa.Column("some_col", sa.Integer(), nullable=True))

def downgrade() -> None:
    # 역방향도 안전하게: 있을 때만 삭제
    if _has_column("challenge_rounds", "address"):
        op.drop_column("challenge_rounds", "address")
