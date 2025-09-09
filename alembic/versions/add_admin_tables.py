"""Add missing admin tables

Revision ID: add_admin_tables
Revises: dd6bdf057ac0
Create Date: 2025-09-04 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123456789'
down_revision: Union[str, Sequence[str], None] = '0a0b993352f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create admin_requests table if missing
    if not inspector.has_table('admin_requests'):
        op.create_table('admin_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='admin_request_status'), nullable=False, server_default='pending'),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_admin_requests_user_id'), 'admin_requests', ['user_id'], unique=False)

    # Create admin_audit_log table if missing
    if not inspector.has_table('admin_audit_log'):
        op.create_table('admin_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('target_type', sa.String(length=100), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_admin_audit_log_admin_id'), 'admin_audit_log', ['admin_id'], unique=False)
        op.create_index(op.f('ix_admin_audit_log_created_at'), 'admin_audit_log', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_admin_audit_log_created_at'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_admin_id'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
    op.drop_index(op.f('ix_admin_requests_user_id'), table_name='admin_requests')
    op.drop_table('admin_requests')
