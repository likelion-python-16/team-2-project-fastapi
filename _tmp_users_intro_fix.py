from alembic import op
import sqlalchemy as sa

revision = "2f59e5535cb0"
down_revision = "ef8de79e440f"
branch_labels = None
depends_on = None

def upgrade():
    # NULL 값을 빈 문자열로 채우기
    op.execute("UPDATE users SET introduction = '' WHERE introduction IS NULL")

    # NOT NULL로 전환
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("introduction", existing_type=sa.Text(), nullable=False)

def downgrade():
    # 되돌릴 때 다시 NULL 허용
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("introduction", existing_type=sa.Text(), nullable=True)
