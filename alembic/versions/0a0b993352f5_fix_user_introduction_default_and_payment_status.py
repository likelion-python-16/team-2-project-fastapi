"""Fix user introduction default and payment status enum

Revision ID: 0a0b993352f5
Revises: 01ecdd0c4d93
Create Date: 2025-08-27 12:30:02.642680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a0b993352f5'
down_revision: Union[str, Sequence[str], None] = '01ecdd0c4d93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update existing NULL introduction values to empty string
    # MySQL TEXT columns cannot have DEFAULT values, so we handle it in application logic
    conn = op.get_bind()
    
    # Update any existing NULL values to empty string
    conn.execute(sa.text("UPDATE users SET introduction = '' WHERE introduction IS NULL"))
    
    # Ensure column is NOT NULL (no server_default needed)
    op.alter_column('users', 'introduction',
                   existing_type=sa.TEXT(),
                   nullable=False)

    # 2. Fix timestamp columns to use DEFAULT instead of server_default (following TimestampMixin pattern)
    op.execute("ALTER TABLE users MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    op.execute("ALTER TABLE users MODIFY COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    
    # 3. Update PaymentStatus enum to include 'completed'
    # Check if 'completed' status already exists in payments table
    result = conn.execute(sa.text("SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='payments' AND COLUMN_NAME='status'")).fetchone()
    
    if result and 'completed' not in result[0]:
        # Add 'completed' to the enum
        op.execute("ALTER TABLE payments MODIFY COLUMN status ENUM('pending','success','completed','failed','cancelled','refunded','partial_refunded') NOT NULL")


def downgrade() -> None:
    # 1. Allow NULL values in users.introduction column (reverting NOT NULL constraint)
    op.alter_column('users', 'introduction',
                   existing_type=sa.TEXT(),
                   nullable=True)
    
    # 2. Revert timestamp columns to no default (original broken state)
    op.execute("ALTER TABLE users MODIFY COLUMN created_at DATETIME NOT NULL")
    op.execute("ALTER TABLE users MODIFY COLUMN updated_at DATETIME NOT NULL")

    # 3. Remove 'completed' from PaymentStatus enum if it was added
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='payments' AND COLUMN_NAME='status'")).fetchone()
    
    if result and 'completed' in result[0]:
        # Remove 'completed' from the enum
        op.execute("ALTER TABLE payments MODIFY COLUMN status ENUM('pending','success','failed','cancelled','refunded','partial_refunded') NOT NULL")