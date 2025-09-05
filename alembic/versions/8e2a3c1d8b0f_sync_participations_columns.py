"""Sync participations table to current model

Adds missing columns used by the application to avoid 1054 errors.

Revision ID: 8e2a3c1d8b0f
Revises: 8e2a3c1d8b0e
Create Date: 2025-09-05 01:46:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '8e2a3c1d8b0f'
down_revision = '8e2a3c1d8b0e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('participations')}

    # Enums
    role_enum = sa.Enum('creator','participant','manager','moderator', name='participation_role_enum')
    status_enum = sa.Enum('pending','payment_pending','active','paused','completed','cancelled','expelled','payment_failed', name='participation_status_enum')
    cycle_enum = sa.Enum('entry_fee','monthly','free', name='payment_cycle_enum')
    leave_enum = sa.Enum('voluntary','kicked','payment_failure','rule_violation','inactivity', name='leave_type_enum')

    def add_if_missing(name, column):
        if name not in cols:
            op.add_column('participations', column)

    # Core columns that may be missing on older DBs
    add_if_missing('role', sa.Column('role', role_enum, nullable=False, server_default='participant'))
    add_if_missing('status', sa.Column('status', status_enum, nullable=False, server_default='pending'))
    add_if_missing('joined_at', sa.Column('joined_at', sa.DateTime(), nullable=False))
    add_if_missing('activated_at', sa.Column('activated_at', sa.DateTime(), nullable=True))
    add_if_missing('completed_at', sa.Column('completed_at', sa.DateTime(), nullable=True))
    add_if_missing('left_at', sa.Column('left_at', sa.DateTime(), nullable=True))
    add_if_missing('payment_cycle', sa.Column('payment_cycle', cycle_enum, nullable=True))
    add_if_missing('next_payment_date', sa.Column('next_payment_date', sa.Date(), nullable=True))
    add_if_missing('payment_failed_count', sa.Column('payment_failed_count', sa.Integer(), nullable=False, server_default='0'))
    add_if_missing('total_paid_amount', sa.Column('total_paid_amount', sa.Integer(), nullable=False, server_default='0'))
    add_if_missing('progress_rate', sa.Column('progress_rate', sa.Float(), nullable=False, server_default='0'))
    add_if_missing('attendance_count', sa.Column('attendance_count', sa.Integer(), nullable=False, server_default='0'))
    add_if_missing('total_rounds', sa.Column('total_rounds', sa.Integer(), nullable=True))
    add_if_missing('leave_type', sa.Column('leave_type', leave_enum, nullable=True))
    add_if_missing('leave_reason', sa.Column('leave_reason', sa.Text(), nullable=True))
    add_if_missing('kicked_by', sa.Column('kicked_by', sa.Integer(), nullable=True))
    add_if_missing('is_notification_enabled', sa.Column('is_notification_enabled', sa.Boolean(), nullable=False, server_default='1'))
    add_if_missing('auto_payment_enabled', sa.Column('auto_payment_enabled', sa.Boolean(), nullable=False, server_default='1'))
    add_if_missing('join_motivation', sa.Column('join_motivation', sa.Text(), nullable=True))

    # Drop server defaults to match app behavior
    for n in ['role','status','payment_failed_count','total_paid_amount','progress_rate','attendance_count','is_notification_enabled','auto_payment_enabled']:
        try:
            op.alter_column('participations', n, server_default=None)
        except Exception:
            pass


def downgrade() -> None:
    # Conservative: don't drop columns automatically
    pass

