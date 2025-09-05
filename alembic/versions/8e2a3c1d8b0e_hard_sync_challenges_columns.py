"""Hard-sync challenges table to match current model

Adds any missing columns and indexes found in production DBs that predate
recent schema changes. Safe to re-run; checks existing state before DDL.

Revision ID: 8e2a3c1d8b0e
Revises: 8e2a3c1d8b0d
Create Date: 2025-09-05 01:34:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '8e2a3c1d8b0e'
down_revision = '8e2a3c1d8b0d'
branch_labels = None
depends_on = None


def _cols():
    bind = op.get_bind()
    insp = inspect(bind)
    return {c['name'] for c in insp.get_columns('challenges')}, insp


def upgrade() -> None:
    cols, insp = _cols()

    # Enums (will no-op if already created by earlier migrations)
    status_enum = sa.Enum('draft', 'recruiting', 'active', 'completed', 'cancelled', 'closed', name='challenge_status_enum')
    mode_enum = sa.Enum('online', 'offline', 'hybrid', name='challenge_mode_enum')
    payment_enum = sa.Enum('free', 'entry_fee', 'monthly_fee', 'both', name='payment_type_enum')

    # Core columns expected by the current model
    add_plan = []
    def add_if_missing(name, col):
        if name not in cols:
            add_plan.append((name, col))

    add_if_missing('title', sa.Column('title', sa.String(length=200), nullable=False))
    add_if_missing('description', sa.Column('description', sa.Text(), nullable=True))
    add_if_missing('creator_id', sa.Column('creator_id', sa.Integer(), nullable=False))
    add_if_missing('start_date', sa.Column('start_date', sa.Date(), nullable=False))
    add_if_missing('end_date', sa.Column('end_date', sa.Date(), nullable=False))
    add_if_missing('status', sa.Column('status', status_enum, nullable=False, server_default='draft'))

    add_if_missing('min_participants', sa.Column('min_participants', sa.Integer(), nullable=False, server_default='1'))
    add_if_missing('max_participants', sa.Column('max_participants', sa.Integer(), nullable=True))
    add_if_missing('current_participants', sa.Column('current_participants', sa.Integer(), nullable=False, server_default='0'))

    add_if_missing('payment_type', sa.Column('payment_type', payment_enum, nullable=False, server_default='free'))
    add_if_missing('entry_fee', sa.Column('entry_fee', sa.Integer(), nullable=False, server_default='0'))
    add_if_missing('monthly_fee', sa.Column('monthly_fee', sa.Integer(), nullable=False, server_default='0'))

    add_if_missing('mode', sa.Column('mode', mode_enum, nullable=False, server_default='online'))
    add_if_missing('total_rounds', sa.Column('total_rounds', sa.Integer(), nullable=True))
    add_if_missing('min_participation_rate', sa.Column('min_participation_rate', sa.Integer(), nullable=False, server_default='80'))

    add_if_missing('default_zoom_link', sa.Column('default_zoom_link', sa.Text(), nullable=True))
    add_if_missing('default_place_name', sa.Column('default_place_name', sa.String(length=200), nullable=True))
    add_if_missing('default_address', sa.Column('default_address', sa.String(length=300), nullable=True))
    add_if_missing('default_latitude', sa.Column('default_latitude', sa.Float(), nullable=True))
    add_if_missing('default_longitude', sa.Column('default_longitude', sa.Float(), nullable=True))
    add_if_missing('same_place_for_all_rounds', sa.Column('same_place_for_all_rounds', sa.Boolean(), nullable=False, server_default='0'))

    add_if_missing('use_reward', sa.Column('use_reward', sa.Boolean(), nullable=False, server_default='0'))
    add_if_missing('reward_description', sa.Column('reward_description', sa.Text(), nullable=True))
    add_if_missing('cover_image_url', sa.Column('cover_image_url', sa.Text(), nullable=True))

    add_if_missing('require_approval', sa.Column('require_approval', sa.Boolean(), nullable=True))
    add_if_missing('is_public', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='1'))

    add_if_missing('completed_at', sa.Column('completed_at', sa.DateTime(), nullable=True))
    add_if_missing('is_settlement_completed', sa.Column('is_settlement_completed', sa.Boolean(), nullable=True, server_default='0'))
    add_if_missing('settlement_completed_at', sa.Column('settlement_completed_at', sa.DateTime(), nullable=True))

    add_if_missing('is_deleted', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
    add_if_missing('deleted_at', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    add_if_missing('deleted_by', sa.Column('deleted_by', sa.Integer(), nullable=True))

    # created_at/updated_at는 보통 이미 존재. 누락됐다면 추가(서버 now 기본값은 부여하지 않음)
    add_if_missing('created_at', sa.Column('created_at', sa.DateTime(), nullable=True))
    add_if_missing('updated_at', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Apply additions
    for name, column in add_plan:
        op.add_column('challenges', column)

    # Remove temporary server_defaults added above to match app behavior
    # Only for columns we added in this migration
    _, insp2 = _cols()
    def drop_default(col_name):
        try:
            op.alter_column('challenges', col_name, server_default=None)
        except Exception:
            pass
    for n in ['status','min_participants','current_participants','payment_type','entry_fee','monthly_fee','mode',
              'min_participation_rate','same_place_for_all_rounds','use_reward','is_public','is_settlement_completed','is_deleted']:
        drop_default(n)

    # Ensure helpful indexes
    idx_names = {ix['name'] for ix in insp2.get_indexes('challenges')}
    def ensure_index(name, cols):
        if name not in idx_names:
            op.create_index(name, 'challenges', cols)
    ensure_index('ix_challenge_status_date', ['status', 'start_date'])
    ensure_index('ix_challenge_creator_status', ['creator_id', 'status'])
    ensure_index('ix_challenge_payment_type', ['payment_type'])
    ensure_index('ix_challenge_participants', ['current_participants', 'max_participants'])
    ensure_index('ix_challenge_public', ['is_public', 'is_deleted'])


def downgrade() -> None:
    # Conservative: do not drop columns in downgrade to avoid data loss.
    # Only drop indexes created here.
    bind = op.get_bind()
    insp = inspect(bind)
    idx_names = {ix['name'] for ix in insp.get_indexes('challenges')}
    for name in ['ix_challenge_status_date','ix_challenge_creator_status','ix_challenge_payment_type','ix_challenge_participants','ix_challenge_public']:
        if name in idx_names:
            op.drop_index(name, table_name='challenges')

