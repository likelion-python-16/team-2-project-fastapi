"""add cover_image_url to challenges

Revision ID: 8e2a3c1d8b0a
Revises: 20250905_user_rounds_enh
Create Date: 2025-09-05 01:05:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8e2a3c1d8b0a"
down_revision = "20250905_user_rounds_enh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "challenges",
        "cover_image_url",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )

def downgrade() -> None:
    op.alter_column(
        "challenges",
        "cover_image_url",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )