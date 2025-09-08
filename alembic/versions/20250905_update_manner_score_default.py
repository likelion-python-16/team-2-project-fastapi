"""update manner score default to 30

Revision ID: update_manner_score_default_20250905
Revises: add_report_auto_eval_20250905
Create Date: 2025-09-05 12:00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'manner_score_30'
down_revision = 'dd6bdf057ac0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 사용자들의 매너점수를 0에서 30으로 업데이트
    op.execute("UPDATE users SET manner_score = 30.0 WHERE manner_score = 0.0")
    
    # 기본값을 30.0으로 변경
    op.alter_column('users', 'manner_score', existing_type=sa.Float(), server_default='30.0')


def downgrade() -> None:
    # 기본값을 0.0으로 되돌림
    op.alter_column('users', 'manner_score', existing_type=sa.Float(), server_default='0.0')
    
    # 매너점수를 30에서 0으로 되돌림 (선택사항)
    op.execute("UPDATE users SET manner_score = 0.0 WHERE manner_score = 30.0")