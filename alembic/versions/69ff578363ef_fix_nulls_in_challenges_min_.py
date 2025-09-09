"""fix nulls in challenges.min_participants before NOT NULL

Revision ID: 69ff578363ef
Revises: 0356e820adef
Create Date: 2025-09-08 14:53:59.514081

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "69ff578363ef"
down_revision = '877172f11b1f'
branch_labels = None
depends_on = None

def upgrade():
    # NULL 데이터 먼저 정리
    op.execute("UPDATE challenges SET min_participants = 1 WHERE min_participants IS NULL")

    # 컬럼을 NOT NULL로 변경
    op.alter_column(
        "challenges",
        "min_participants",
        existing_type=mysql.INTEGER(),
        nullable=False,
        existing_nullable=True,
    )

def downgrade():
    op.alter_column(
        "challenges",
        "min_participants",
        existing_type=mysql.INTEGER(),
        nullable=True,
    )