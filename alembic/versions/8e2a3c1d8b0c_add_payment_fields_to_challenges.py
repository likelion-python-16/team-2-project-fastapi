"""add payment_type/entry_fee/monthly_fee to challenges (with backfill)

Revision ID: 8e2a3c1d8b0c
Revises: 8e2a3c1d8b0b
Create Date: 2025-09-05 01:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '8e2a3c1d8b0c'
down_revision = 'd3cb72e56b3b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    cols = {c['name'] for c in insp.get_columns('challenges')}

    # Enums
    payment_enum = sa.Enum('free', 'entry_fee', 'monthly_fee', 'both', name='payment_type_enum')

    # Add columns if missing (with safe server defaults during DDL)
    if 'payment_type' not in cols:
        op.add_column('challenges', sa.Column('payment_type', payment_enum, nullable=False, server_default='free'))
    if 'entry_fee' not in cols:
        op.add_column('challenges', sa.Column('entry_fee', sa.Integer(), nullable=False, server_default='0', comment='원'))
    if 'monthly_fee' not in cols:
        op.add_column('challenges', sa.Column('monthly_fee', sa.Integer(), nullable=False, server_default='0', comment='원'))

    # Backfill from legacy columns if present (fee -> monthly_fee, participation_fee -> entry_fee)
    cols = {c['name'] for c in insp.get_columns('challenges')}
    has_legacy_fee = 'fee' in cols
    has_legacy_part = 'participation_fee' in cols

    # Build and run backfill UPDATE
    set_parts = []
    if has_legacy_part:
        set_parts.append("entry_fee = COALESCE(participation_fee, entry_fee)")
    if has_legacy_fee:
        set_parts.append("monthly_fee = COALESCE(fee, monthly_fee)")
    if set_parts:
        op.execute(text(f"UPDATE challenges SET {', '.join(set_parts)}"))

    # Derive payment_type from fees where not already meaningful
    # both if both > 0, entry_fee if entry_fee>0, monthly_fee if monthly_fee>0, else free
    op.execute(text(
        """
        UPDATE challenges
        SET payment_type = CASE
            WHEN COALESCE(entry_fee,0) > 0 AND COALESCE(monthly_fee,0) > 0 THEN 'both'
            WHEN COALESCE(entry_fee,0) > 0 THEN 'entry_fee'
            WHEN COALESCE(monthly_fee,0) > 0 THEN 'monthly_fee'
            ELSE 'free'
        END
        """
    ))

    # Drop server defaults to match application behavior
    op.alter_column('challenges', 'payment_type', server_default=None)
    op.alter_column('challenges', 'entry_fee', server_default=None)
    op.alter_column('challenges', 'monthly_fee', server_default=None)

    # Ensure index on payment_type exists
    idx_names = {ix['name'] for ix in insp.get_indexes('challenges')}
    if 'ix_challenge_payment_type' not in idx_names:
        op.create_index('ix_challenge_payment_type', 'challenges', ['payment_type'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = {ix['name'] for ix in insp.get_indexes('challenges')}
    if 'ix_challenge_payment_type' in idx_names:
        op.drop_index('ix_challenge_payment_type', table_name='challenges')

    cols = {c['name'] for c in insp.get_columns('challenges')}
    if 'payment_type' in cols:
        op.drop_column('challenges', 'payment_type')
    if 'entry_fee' in cols:
        op.drop_column('challenges', 'entry_fee')
    if 'monthly_fee' in cols:
        op.drop_column('challenges', 'monthly_fee')

