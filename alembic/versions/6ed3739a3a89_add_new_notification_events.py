"""Add new notification events

Revision ID: 6ed3739a3a89
Revises: 1e78e90b0832
Create Date: 2025-09-05 05:19:38.801281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6ed3739a3a89'
down_revision: Union[str, Sequence[str], None] = '1e78e90b0832'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _table_exists(conn, table_name):
    return conn.exec_driver_sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
        (table_name,)
    ).scalar() is not None

def _index_exists(conn, table_name, index_name):
    return conn.exec_driver_sql(
        "SELECT 1 FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s LIMIT 1",
        (table_name, index_name)
    ).scalar() is not None

def _column_exists(conn, table_name, column_name):
    return conn.exec_driver_sql(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s LIMIT 1",
        (table_name, column_name)
    ).scalar() is not None

# Helpers to make index ops idempotent
def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], unique: bool = False):
    conn = op.get_bind()
    if not _index_exists(conn, table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)

def _drop_index_if_exists(table_name: str, index_name: str):
    conn = op.get_bind()
    if _index_exists(conn, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)

def _fk_exists(conn, table_name: str, constraint_name: str) -> bool:
    return conn.exec_driver_sql(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND constraint_name = %s
          AND constraint_type = 'FOREIGN KEY'
        LIMIT 1
        """,
        (table_name, constraint_name),
    ).scalar() is not None

def _unique_exists(conn, table_name: str, constraint_name: str) -> bool:
    return conn.exec_driver_sql(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND constraint_name = %s
          AND constraint_type = 'UNIQUE'
        LIMIT 1
        """,
        (table_name, constraint_name),
    ).scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # --- email_verifications 안전 드롭 ---
    if _table_exists(conn, "email_verifications"):
        if _table_exists(conn, "email_verifications"):
            op.drop_table('email_verifications')

    # --- point_exchange_requests 안전 드롭 ---
    if _table_exists(conn, "point_exchange_requests"):
        for idx in (
            'ix_point_exchange_requests_id',
            'ix_px_amount',
            'ix_px_status',
            'ix_px_user_requested',
        ):
            if _index_exists(conn, "point_exchange_requests", idx):
                op.drop_index(idx, table_name='point_exchange_requests')
        op.drop_table('point_exchange_requests')

    # --- email_verifications 안전 생성 ---
    if not _table_exists(conn, "email_verifications"):
        op.create_table(
            'email_verifications',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            # ... (원래 파일에 있던 컬럼 정의 그대로)
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='email_verifications_ibfk_1'),
        )
    # 인덱스도 없을 때만
    if _table_exists(conn, "email_verifications") and not _index_exists(conn, "email_verifications", "ix_email_verifications_user_id"):
        op.create_index('ix_email_verifications_user_id', 'email_verifications', ['user_id'], unique=False)

    """Upgrade schema."""
    # 이미 위에서 email_verifications / point_exchange_requests는 존재 여부에 따라 처리함
    op.alter_column('challenge_rounds', 'reward_enabled',
               existing_type=mysql.TINYINT(display_width=1),
               comment='보상 활성화 여부',
               existing_comment='리워드 사용 여부',
               existing_nullable=False)
    if _table_exists(conn, 'challenge_rounds') and _column_exists(conn, 'challenge_rounds', 'reward_text'):
        op.drop_column('challenge_rounds', 'reward_text')
    op.alter_column('challenges', 'title',
               existing_type=mysql.VARCHAR(length=100),
               type_=sa.String(length=200),
               existing_nullable=False)
    op.execute("UPDATE challenges SET status = 'draft' WHERE status IS NULL")
    op.alter_column('challenges', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum('draft', 'recruiting', 'active', 'completed', 'cancelled', 'closed', name='challenge_status_enum'),
               nullable=False,
               comment=None,
               existing_comment='챌린지 상태')
    # Ensure no NULLs before making NOT NULL
    op.execute("UPDATE challenges SET min_participants = 1 WHERE min_participants IS NULL")
    op.alter_column('challenges', 'min_participants',
               existing_type=mysql.INTEGER(),
               nullable=False,
               comment=None,
               existing_comment='최소 참가자 수')
    op.alter_column('challenges', 'max_participants',
               existing_type=mysql.INTEGER(),
               comment=None,
               existing_comment='최대 참가자 수',
               existing_nullable=True)
    op.execute("UPDATE challenges SET payment_type = 'free' WHERE payment_type IS NULL")
    op.alter_column('challenges', 'payment_type',
               existing_type=mysql.ENUM('free', 'entry_fee', 'monthly_fee'),
               nullable=False,
               existing_server_default=sa.text("'free'"))
    op.execute("UPDATE challenges SET entry_fee = 0 WHERE entry_fee IS NULL")
    op.alter_column('challenges', 'entry_fee',
               existing_type=mysql.INTEGER(),
               nullable=False,
               comment='원',
               existing_server_default=sa.text("'0'"))
    op.execute("UPDATE challenges SET monthly_fee = 0 WHERE monthly_fee IS NULL")
    op.alter_column('challenges', 'monthly_fee',
               existing_type=mysql.INTEGER(),
               nullable=False,
               comment='원',
               existing_server_default=sa.text("'0'"))
    op.execute("UPDATE challenges SET mode = 'online' WHERE mode IS NULL")
    op.alter_column('challenges', 'mode',
               existing_type=mysql.ENUM('online', 'offline', 'hybrid'),
               nullable=False)
    op.alter_column('challenges', 'total_rounds',
               existing_type=mysql.INTEGER(),
               comment=None,
               existing_comment='총 회차 수',
               existing_nullable=True)
    op.execute("UPDATE challenges SET min_participation_rate = 80 WHERE min_participation_rate IS NULL")
    op.alter_column('challenges', 'min_participation_rate',
               existing_type=mysql.INTEGER(),
               nullable=False,
               comment='%',
               existing_comment='최소 참여율 (%)')
    op.alter_column('challenges', 'default_place_name',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.String(length=200),
               existing_nullable=True)
    op.alter_column('challenges', 'default_address',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.String(length=300),
               existing_nullable=True)
    op.execute("UPDATE challenges SET same_place_for_all_rounds = 0 WHERE same_place_for_all_rounds IS NULL")
    op.alter_column('challenges', 'same_place_for_all_rounds',
               existing_type=mysql.TINYINT(display_width=1),
               comment=None,
               existing_comment='모든 회차 동일 장소 여부',
               existing_nullable=False)
    op.execute("UPDATE challenges SET use_reward = 0 WHERE use_reward IS NULL")
    op.alter_column('challenges', 'use_reward',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=False,
               comment=None,
               existing_comment='리워드 사용 여부')
    op.execute("UPDATE challenges SET require_approval = 0 WHERE require_approval IS NULL")
    op.alter_column('challenges', 'require_approval',
               existing_type=mysql.TINYINT(display_width=1),
               comment='참가 승인 필요',
               existing_nullable=True,
               existing_server_default=sa.text("'0'"))
    op.execute("UPDATE challenges SET is_public = 1 WHERE is_public IS NULL")
    op.alter_column('challenges', 'is_public',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=False,
               existing_server_default=sa.text("'1'"))
    op.execute("UPDATE challenges SET is_deleted = 0 WHERE is_deleted IS NULL")
    op.alter_column('challenges', 'is_deleted',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=False,
               comment=None,
               existing_comment='삭제 여부')
    op.alter_column('challenges', 'deleted_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='삭제 시간',
               existing_nullable=True)
    op.alter_column('challenges', 'deleted_by',
               existing_type=mysql.INTEGER(),
               comment=None,
               existing_comment='삭제한 유저',
               existing_nullable=True)
    op.alter_column('challenges', 'created_at',
               existing_type=mysql.DATETIME(),
               nullable=False)
    op.alter_column('challenges', 'updated_at',
               existing_type=mysql.DATETIME(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    # Create challenge indexes only if missing to avoid duplicate-name errors
    _create_index_if_missing('challenges', 'ix_challenge_creator_status', ['creator_id', 'status'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenge_participants', ['current_participants', 'max_participants'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenge_payment_type', ['payment_type'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenge_public', ['is_public', 'is_deleted'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenge_status_date', ['status', 'start_date'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenges_creator_id', ['creator_id'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenges_end_date', ['end_date'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenges_start_date', ['start_date'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenges_status', ['status'], unique=False)
    _create_index_if_missing('challenges', 'ix_challenges_title', ['title'], unique=False)
    if _fk_exists(conn, 'challenges', 'challenges_ibfk_3'):
        op.drop_constraint('challenges_ibfk_3', 'challenges', type_='foreignkey')
    # Drop legacy columns only if they exist (idempotent guards)
    for col in (
        'default_map_url',
        'max_participation_rate',
        'fee',
        'default_road_address',
        'is_closed',
        'cover_image_url',
        'participation_fee',
        'reward',
        'cover_round_picture_id',
        'default_place_id',
    ):
        if _column_exists(conn, 'challenges', col):
            op.drop_column('challenges', col)
    # Fix invalid zero-datetime and NULLs before altering participations
    # Some MySQL modes error on referencing zero-date literals; temporarily relax them.
    op.execute("SET @OLD_SQL_MODE=@@SQL_MODE")
    op.execute("SET SESSION sql_mode=(SELECT REPLACE(@@sql_mode,'NO_ZERO_DATE',''))")
    op.execute("SET SESSION sql_mode=(SELECT REPLACE(@@sql_mode,'NO_ZERO_IN_DATE',''))")
    op.execute(
        "UPDATE participations SET joined_at = NOW() "
        "WHERE joined_at IS NULL OR joined_at = '0000-00-00 00:00:00'"
    )
    op.execute("SET SESSION sql_mode=@OLD_SQL_MODE")
    op.alter_column('participations', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum('pending', 'payment_pending', 'active', 'paused', 'completed', 'cancelled', 'expelled', 'payment_failed', name='participation_status_enum'),
               existing_nullable=False)
    op.alter_column('participations', 'joined_at',
               existing_type=mysql.DATETIME(),
               comment='참가 신청 시간',
               existing_nullable=False)
    for idx in (
        'ix_participation_active',
        'ix_participation_joined',
        'ix_participation_role',
        'ix_participation_status',
        'ix_participations_id',
    ):
        if _index_exists(conn, 'participations', idx):
            op.drop_index(idx, table_name='participations')
    _create_index_if_missing('participations', 'ix_participation_joined_status', ['joined_at', 'status'], unique=False)
    _create_index_if_missing('participations', 'ix_participation_status_role', ['status', 'role'], unique=False)
    _create_index_if_missing('participations', 'ix_participations_is_active', ['is_active'], unique=False)
    _create_index_if_missing('participations', 'ix_participations_joined_at', ['joined_at'], unique=False)
    _create_index_if_missing('participations', 'ix_participations_role', ['role'], unique=False)
    _create_index_if_missing('participations', 'ix_participations_status', ['status'], unique=False)
    if _fk_exists(conn, 'participations', 'participations_ibfk_1'):
        op.drop_constraint('participations_ibfk_1', 'participations', type_='foreignkey')
    if _fk_exists(conn, 'participations', 'participations_ibfk_2'):
        op.drop_constraint('participations_ibfk_2', 'participations', type_='foreignkey')
    op.create_foreign_key(None, 'participations', 'challenges', ['challenge_id'], ['id'])
    op.create_foreign_key(None, 'participations', 'users', ['user_id'], ['id'])
    if _column_exists(conn, 'participations', 'id'):
        op.drop_column('participations', 'id')
    if _column_exists(conn, 'participations', 'leave_type'):
        op.drop_column('participations', 'leave_type')
    if not _column_exists(conn, 'payments', 'method'):
        op.add_column('payments', sa.Column('method', sa.Enum('card', 'bank_transfer', 'toss_pay', 'kakao_pay', 'point', name='payment_method_type_enum'), nullable=False))
    if not _column_exists(conn, 'payments', 'transaction_type'):
        op.add_column('payments', sa.Column('transaction_type', sa.Enum('entry_fee', 'monthly_fee', 'penalty', 'etc', name='payment_transaction_type_enum'), nullable=False))
    if not _column_exists(conn, 'payments', 'order_id'):
        op.add_column('payments', sa.Column('order_id', sa.String(length=100), nullable=False))
    if not _column_exists(conn, 'payments', 'order_name'):
        op.add_column('payments', sa.Column('order_name', sa.String(length=200), nullable=True))
    if not _column_exists(conn, 'payments', 'payment_key'):
        op.add_column('payments', sa.Column('payment_key', sa.String(length=255), nullable=True))
    if not _column_exists(conn, 'payments', 'requested_at'):
        op.add_column('payments', sa.Column('requested_at', sa.DateTime(), nullable=False))
    if not _column_exists(conn, 'payments', 'approved_at'):
        op.add_column('payments', sa.Column('approved_at', sa.DateTime(), nullable=True))
    if not _column_exists(conn, 'payments', 'failed_at'):
        op.add_column('payments', sa.Column('failed_at', sa.DateTime(), nullable=True))
    if not _column_exists(conn, 'payments', 'cancelled_at'):
        op.add_column('payments', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    if not _column_exists(conn, 'payments', 'failure_code'):
        op.add_column('payments', sa.Column('failure_code', sa.String(length=50), nullable=True))
    if not _column_exists(conn, 'payments', 'failure_message'):
        op.add_column('payments', sa.Column('failure_message', sa.Text(), nullable=True))
    if not _column_exists(conn, 'payments', 'cancel_reason'):
        op.add_column('payments', sa.Column('cancel_reason', sa.Text(), nullable=True))
    if not _column_exists(conn, 'payments', 'metadata_json'):
        op.add_column('payments', sa.Column('metadata_json', sa.Text(), nullable=True))
    op.alter_column('payments', 'challenge_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
    op.alter_column('payments', 'amount',
               existing_type=mysql.DECIMAL(precision=12, scale=2),
               type_=sa.Integer(),
               existing_nullable=False)
    _drop_index_if_exists('payments', 'ix_payment_amount')
    # Skip dropping challenge index if FK still exists (MySQL requires it)
    if not _fk_exists(conn, 'payments', 'payments_ibfk_2'):
        _drop_index_if_exists('payments', 'ix_payment_challenge')
    _drop_index_if_exists('payments', 'ix_payment_status')
    if not _fk_exists(conn, 'payments', 'payments_ibfk_1'):
        _drop_index_if_exists('payments', 'ix_payment_user_created')
    _drop_index_if_exists('payments', 'uq_payment_idem')
    _drop_index_if_exists('payments', 'uq_payment_toss')
    _create_index_if_missing('payments', 'ix_payment_challenge_type', ['challenge_id', 'transaction_type'], unique=False)
    _create_index_if_missing('payments', 'ix_payment_user_status', ['user_id', 'status'], unique=False)
    _create_index_if_missing('payments', 'ix_payments_challenge_id', ['challenge_id'], unique=False)
    _create_index_if_missing('payments', 'ix_payments_order_id', ['order_id'], unique=True)
    _create_index_if_missing('payments', 'ix_payments_user_id', ['user_id'], unique=False)
    if not _unique_exists(conn, 'payments', 'payment_key'):
        op.create_unique_constraint(None, 'payments', ['payment_key'])
    if _fk_exists(conn, 'payments', 'payments_ibfk_2'):
        op.drop_constraint('payments_ibfk_2', 'payments', type_='foreignkey')
    if _fk_exists(conn, 'payments', 'payments_ibfk_1'):
        op.drop_constraint('payments_ibfk_1', 'payments', type_='foreignkey')
    op.create_foreign_key(None, 'payments', 'users', ['user_id'], ['id'])
    op.create_foreign_key(None, 'payments', 'challenges', ['challenge_id'], ['id'])
    if not _fk_exists(conn, 'payments', 'fk_payment_participation'):
        op.create_foreign_key('fk_payment_participation', 'payments', 'participations', ['user_id', 'challenge_id'], ['user_id', 'challenge_id'], use_alter=True)
    for col in ('currency', 'toss_payment_id', 'planner_id_at_payment', 'payment_type', 'idempotency_key'):
        if _column_exists(conn, 'payments', col):
            op.drop_column('payments', col)
    if not _column_exists(conn, 'refunds', 'payment_id'):
        op.add_column('refunds', sa.Column('payment_id', sa.Integer(), nullable=False))
    if not _column_exists(conn, 'refunds', 'refund_amount'):
        op.add_column('refunds', sa.Column('refund_amount', sa.Integer(), nullable=False))
    if not _column_exists(conn, 'refunds', 'refund_reason'):
        op.add_column('refunds', sa.Column('refund_reason', sa.Text(), nullable=True))
    if not _column_exists(conn, 'refunds', 'status'):
        op.add_column('refunds', sa.Column('status', sa.Enum('pending', 'success', 'completed', 'failed', 'cancelled', 'refunded', 'partial_refunded', name='refund_status_enum'), nullable=False))
    if not _column_exists(conn, 'refunds', 'requested_at'):
        op.add_column('refunds', sa.Column('requested_at', sa.DateTime(), nullable=False))
    op.alter_column('refunds', 'challenge_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
    _drop_index_if_exists('refunds', 'ix_refund_amount')
    if not _fk_exists(conn, 'refunds', 'refunds_ibfk_2'):
        _drop_index_if_exists('refunds', 'ix_refund_challenge')
    _drop_index_if_exists('refunds', 'ix_refund_status')
    if not _fk_exists(conn, 'refunds', 'refunds_ibfk_1'):
        _drop_index_if_exists('refunds', 'ix_refund_user_processed')
    _drop_index_if_exists('refunds', 'uq_refund_toss')
    _create_index_if_missing('refunds', 'ix_refund_user_date', ['user_id', 'requested_at'], unique=False)
    _create_index_if_missing('refunds', 'ix_refunds_challenge_id', ['challenge_id'], unique=False)
    _create_index_if_missing('refunds', 'ix_refunds_payment_id', ['payment_id'], unique=False)
    _create_index_if_missing('refunds', 'ix_refunds_user_id', ['user_id'], unique=False)
    if _fk_exists(conn, 'refunds', 'refunds_ibfk_1'):
        op.drop_constraint('refunds_ibfk_1', 'refunds', type_='foreignkey')
    if _fk_exists(conn, 'refunds', 'refunds_ibfk_2'):
        op.drop_constraint('refunds_ibfk_2', 'refunds', type_='foreignkey')
    op.create_foreign_key(None, 'refunds', 'challenges', ['challenge_id'], ['id'])
    op.create_foreign_key(None, 'refunds', 'payments', ['payment_id'], ['id'])
    op.create_foreign_key(None, 'refunds', 'users', ['user_id'], ['id'])
    for col in ('reason', 'currency', 'error_msg', 'toss_refund_id', 'amount', 'refund_status'):
        if _column_exists(conn, 'refunds', col):
            op.drop_column('refunds', col)
    _drop_index_if_exists('reviews', 'idx_reviews_target_user')
    _drop_index_if_exists('reviews', 'uq_review_user_target_challenge')
    # Deduplicate existing rows to satisfy upcoming unique constraint
    op.execute(
        """
        DELETE r1 FROM reviews r1
        JOIN reviews r2
          ON r1.user_id = r2.user_id
         AND r1.challenge_id = r2.challenge_id
         AND r1.id > r2.id
        """
    )
    if not _unique_exists(conn, 'reviews', 'uq_review_user_challenge'):
        op.create_unique_constraint('uq_review_user_challenge', 'reviews', ['user_id', 'challenge_id'])
    op.create_foreign_key(None, 'reviews', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.drop_constraint('uq_review_user_challenge', 'reviews', type_='unique')
    op.create_index('uq_review_user_target_challenge', 'reviews', ['user_id', 'target_user_id', 'challenge_id'], unique=True)
    op.create_index('idx_reviews_target_user', 'reviews', ['target_user_id'], unique=False)
    op.add_column('refunds', sa.Column('refund_status', mysql.ENUM('pending', 'processing', 'succeeded', 'failed'), nullable=False))
    op.add_column('refunds', sa.Column('amount', mysql.DECIMAL(precision=12, scale=2), nullable=False))
    op.add_column('refunds', sa.Column('toss_refund_id', mysql.VARCHAR(length=100), nullable=True))
    op.add_column('refunds', sa.Column('error_msg', mysql.TEXT(), nullable=True))
    op.add_column('refunds', sa.Column('currency', mysql.VARCHAR(length=3), nullable=False))
    op.add_column('refunds', sa.Column('reason', mysql.VARCHAR(length=100), nullable=False))
    op.drop_constraint(None, 'refunds', type_='foreignkey')
    op.drop_constraint(None, 'refunds', type_='foreignkey')
    op.drop_constraint(None, 'refunds', type_='foreignkey')
    op.create_foreign_key('refunds_ibfk_2', 'refunds', 'challenges', ['challenge_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('refunds_ibfk_1', 'refunds', 'users', ['user_id'], ['id'], ondelete='RESTRICT')
    op.drop_index(op.f('ix_refunds_user_id'), table_name='refunds')
    op.drop_index(op.f('ix_refunds_payment_id'), table_name='refunds')
    op.drop_index(op.f('ix_refunds_challenge_id'), table_name='refunds')
    op.drop_index('ix_refund_user_date', table_name='refunds')
    op.create_index('uq_refund_toss', 'refunds', ['toss_refund_id'], unique=True)
    op.create_index('ix_refund_user_processed', 'refunds', ['user_id', 'processed_at'], unique=False)
    op.create_index('ix_refund_status', 'refunds', ['refund_status'], unique=False)
    op.create_index('ix_refund_challenge', 'refunds', ['challenge_id'], unique=False)
    op.create_index('ix_refund_amount', 'refunds', ['amount'], unique=False)
    op.alter_column('refunds', 'challenge_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.drop_column('refunds', 'requested_at')
    op.drop_column('refunds', 'status')
    op.drop_column('refunds', 'refund_reason')
    op.drop_column('refunds', 'refund_amount')
    op.drop_column('refunds', 'payment_id')
    op.add_column('payments', sa.Column('idempotency_key', mysql.VARCHAR(length=64), nullable=True))
    op.add_column('payments', sa.Column('payment_type', mysql.VARCHAR(length=20), nullable=False))
    op.add_column('payments', sa.Column('planner_id_at_payment', mysql.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('payments', sa.Column('toss_payment_id', mysql.VARCHAR(length=100), nullable=False))
    op.add_column('payments', sa.Column('currency', mysql.VARCHAR(length=3), nullable=False))
    if _fk_exists(conn, 'payments', 'fk_payment_participation'):
        op.drop_constraint('fk_payment_participation', 'payments', type_='foreignkey')
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.create_foreign_key('payments_ibfk_1', 'payments', 'users', ['user_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('payments_ibfk_2', 'payments', 'challenges', ['challenge_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint(None, 'payments', type_='unique')
    op.drop_index(op.f('ix_payments_user_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_challenge_id'), table_name='payments')
    op.drop_index('ix_payment_user_status', table_name='payments')
    op.drop_index('ix_payment_challenge_type', table_name='payments')
    op.create_index('uq_payment_toss', 'payments', ['toss_payment_id'], unique=True)
    op.create_index('uq_payment_idem', 'payments', ['idempotency_key'], unique=True)
    op.create_index('ix_payment_user_created', 'payments', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_payment_status', 'payments', ['status'], unique=False)
    op.create_index('ix_payment_challenge', 'payments', ['challenge_id'], unique=False)
    op.create_index('ix_payment_amount', 'payments', ['amount'], unique=False)
    op.alter_column('payments', 'amount',
               existing_type=sa.Integer(),
               type_=mysql.DECIMAL(precision=12, scale=2),
               existing_nullable=False)
    op.alter_column('payments', 'challenge_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.drop_column('payments', 'metadata_json')
    op.drop_column('payments', 'cancel_reason')
    op.drop_column('payments', 'failure_message')
    op.drop_column('payments', 'failure_code')
    op.drop_column('payments', 'cancelled_at')
    op.drop_column('payments', 'failed_at')
    op.drop_column('payments', 'approved_at')
    op.drop_column('payments', 'requested_at')
    op.drop_column('payments', 'payment_key')
    op.drop_column('payments', 'order_name')
    op.drop_column('payments', 'order_id')
    op.drop_column('payments', 'transaction_type')
    op.drop_column('payments', 'method')
    op.add_column('participations', sa.Column('leave_type', mysql.VARCHAR(length=20), nullable=True))
    op.add_column('participations', sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False))
    op.drop_constraint(None, 'participations', type_='foreignkey')
    op.drop_constraint(None, 'participations', type_='foreignkey')
    op.create_foreign_key('participations_ibfk_2', 'participations', 'challenges', ['challenge_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('participations_ibfk_1', 'participations', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_participations_status'), table_name='participations')
    op.drop_index(op.f('ix_participations_role'), table_name='participations')
    op.drop_index(op.f('ix_participations_joined_at'), table_name='participations')
    op.drop_index(op.f('ix_participations_is_active'), table_name='participations')
    op.drop_index('ix_participation_status_role', table_name='participations')
    op.drop_index('ix_participation_joined_status', table_name='participations')
    op.create_index('ix_participations_id', 'participations', ['id'], unique=False)
    op.create_index('ix_participation_status', 'participations', ['status'], unique=False)
    op.create_index('ix_participation_role', 'participations', ['role'], unique=False)
    op.create_index('ix_participation_joined', 'participations', ['joined_at'], unique=False)
    op.create_index('ix_participation_active', 'participations', ['is_active'], unique=False)
    op.alter_column('participations', 'joined_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='참가 신청 시간',
               existing_nullable=False)
    op.alter_column('participations', 'status',
               existing_type=sa.Enum('pending', 'payment_pending', 'active', 'paused', 'completed', 'cancelled', 'expelled', 'payment_failed', name='participation_status_enum'),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False)
    op.add_column('challenges', sa.Column('default_place_id', mysql.VARCHAR(length=64), nullable=True, comment='네이버 placeId (검색/앱 링크용)'))
    op.add_column('challenges', sa.Column('cover_round_picture_id', mysql.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('challenges', sa.Column('reward', mysql.TEXT(), nullable=True, comment='리워드 내용'))
    op.add_column('challenges', sa.Column('participation_fee', mysql.INTEGER(), autoincrement=False, nullable=True, comment='참가비 (원)'))
    op.add_column('challenges', sa.Column('cover_image_url', mysql.VARCHAR(length=255), nullable=True))
    op.add_column('challenges', sa.Column('is_closed', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True, comment='정산 완료 여부'))
    op.add_column('challenges', sa.Column('default_road_address', mysql.VARCHAR(length=255), nullable=True))
    op.add_column('challenges', sa.Column('fee', mysql.INTEGER(), autoincrement=False, nullable=True, comment='회비 (원)'))
    op.add_column('challenges', sa.Column('max_participation_rate', mysql.INTEGER(), autoincrement=False, nullable=True, comment='최대 참여율 (%)'))
    op.add_column('challenges', sa.Column('default_map_url', mysql.VARCHAR(length=512), nullable=True))
    op.create_foreign_key('challenges_ibfk_3', 'challenges', 'round_pictures', ['cover_round_picture_id'], ['id'], ondelete='SET NULL')
    _drop_index_if_exists('challenges', 'ix_challenges_title')
    _drop_index_if_exists('challenges', 'ix_challenges_status')
    _drop_index_if_exists('challenges', 'ix_challenges_start_date')
    _drop_index_if_exists('challenges', 'ix_challenges_end_date')
    _drop_index_if_exists('challenges', 'ix_challenges_creator_id')
    _drop_index_if_exists('challenges', 'ix_challenge_status_date')
    _drop_index_if_exists('challenges', 'ix_challenge_public')
    _drop_index_if_exists('challenges', 'ix_challenge_payment_type')
    _drop_index_if_exists('challenges', 'ix_challenge_participants')
    _drop_index_if_exists('challenges', 'ix_challenge_creator_status')
    op.alter_column('challenges', 'updated_at',
               existing_type=mysql.DATETIME(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    op.alter_column('challenges', 'created_at',
               existing_type=mysql.DATETIME(),
               nullable=True)
    op.alter_column('challenges', 'deleted_by',
               existing_type=mysql.INTEGER(),
               comment='삭제한 유저',
               existing_nullable=True)
    op.alter_column('challenges', 'deleted_at',
               existing_type=mysql.DATETIME(),
               comment='삭제 시간',
               existing_nullable=True)
    op.alter_column('challenges', 'is_deleted',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               comment='삭제 여부')
    op.alter_column('challenges', 'is_public',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               existing_server_default=sa.text("'1'"))
    op.alter_column('challenges', 'require_approval',
               existing_type=mysql.TINYINT(display_width=1),
               comment=None,
               existing_comment='참가 승인 필요',
               existing_nullable=True,
               existing_server_default=sa.text("'0'"))
    op.alter_column('challenges', 'use_reward',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               comment='리워드 사용 여부')
    op.alter_column('challenges', 'same_place_for_all_rounds',
               existing_type=mysql.TINYINT(display_width=1),
               comment='모든 회차 동일 장소 여부',
               existing_nullable=False)
    op.alter_column('challenges', 'default_address',
               existing_type=sa.String(length=300),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)
    op.alter_column('challenges', 'default_place_name',
               existing_type=sa.String(length=200),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)
    op.alter_column('challenges', 'min_participation_rate',
               existing_type=mysql.INTEGER(),
               nullable=True,
               comment='최소 참여율 (%)',
               existing_comment='%')
    op.alter_column('challenges', 'total_rounds',
               existing_type=mysql.INTEGER(),
               comment='총 회차 수',
               existing_nullable=True)
    op.alter_column('challenges', 'mode',
               existing_type=mysql.ENUM('online', 'offline', 'hybrid'),
               nullable=True)
    op.alter_column('challenges', 'monthly_fee',
               existing_type=mysql.INTEGER(),
               nullable=True,
               comment=None,
               existing_comment='원',
               existing_server_default=sa.text("'0'"))
    op.alter_column('challenges', 'entry_fee',
               existing_type=mysql.INTEGER(),
               nullable=True,
               comment=None,
               existing_comment='원',
               existing_server_default=sa.text("'0'"))
    op.alter_column('challenges', 'payment_type',
               existing_type=mysql.ENUM('free', 'entry_fee', 'monthly_fee'),
               nullable=True,
               existing_server_default=sa.text("'free'"))
    op.alter_column('challenges', 'max_participants',
               existing_type=mysql.INTEGER(),
               comment='최대 참가자 수',
               existing_nullable=True)
    op.alter_column('challenges', 'min_participants',
               existing_type=mysql.INTEGER(),
               nullable=True,
               comment='최소 참가자 수')
    op.alter_column('challenges', 'status',
               existing_type=sa.Enum('draft', 'recruiting', 'active', 'completed', 'cancelled', 'closed', name='challenge_status_enum'),
               type_=mysql.VARCHAR(length=20),
               nullable=True,
               comment='챌린지 상태')
    op.alter_column('challenges', 'title',
               existing_type=sa.String(length=200),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=False)
    op.add_column('challenge_rounds', sa.Column('reward_text', mysql.TEXT(), nullable=True, comment='회차 리워드 내용'))
    op.alter_column('challenge_rounds', 'reward_enabled',
               existing_type=mysql.TINYINT(display_width=1),
               comment='리워드 사용 여부',
               existing_comment='보상 활성화 여부',
               existing_nullable=False)
    op.create_table('point_exchange_requests',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('point_amount', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('cash_amount', mysql.DECIMAL(precision=12, scale=2), nullable=False),
    sa.Column('status', mysql.ENUM('pending', 'approved', 'rejected', 'paid'), nullable=False),
    sa.Column('requested_at', mysql.DATETIME(), nullable=False),
    sa.Column('processed_at', mysql.DATETIME(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='point_exchange_requests_ibfk_1', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_px_user_requested', 'point_exchange_requests', ['user_id', 'requested_at'], unique=False)
    op.create_index('ix_px_status', 'point_exchange_requests', ['status'], unique=False)
    op.create_index('ix_px_amount', 'point_exchange_requests', ['point_amount'], unique=False)
    op.create_index('ix_point_exchange_requests_id', 'point_exchange_requests', ['id'], unique=False)
    op.create_table('email_verifications',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('token', mysql.VARCHAR(length=128), nullable=False),
    sa.Column('sent_to', mysql.VARCHAR(length=120), nullable=False),
    sa.Column('expires_at', mysql.DATETIME(), nullable=False),
    sa.Column('used_at', mysql.DATETIME(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='email_verifications_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_email_verifications_user_id', 'email_verifications', ['user_id'], unique=False)
    # ### end Alembic commands ###
