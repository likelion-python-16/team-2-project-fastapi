"""add report_auto_evals table

Revision ID: add_report_auto_eval_20250905
Revises: 
Create Date: 2025-09-05 00:00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_report_auto_eval_20250905'
down_revision = 'add_participation_is_active_20250905'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum for auto decision
    auto_enum = sa.Enum('true', 'false', 'review', name='report_auto_decision_enum')
    auto_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'report_auto_evals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('comment_text', sa.Text(), nullable=False),
        sa.Column('comment_hash', sa.String(length=64), nullable=False),
        sa.Column('toxic_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rule_flag', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('reporter_trust', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('multi_report_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('auto_decision', auto_enum, nullable=False),
        sa.Column('auto_confidence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('decided_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_report_auto_eval_report', 'report_auto_evals', ['report_id'])
    op.create_index('ix_report_auto_eval_decided_at', 'report_auto_evals', ['decided_at'])
    op.create_index('ix_report_auto_eval_decision', 'report_auto_evals', ['auto_decision'])
    op.create_index('ix_report_auto_eval_comment_hash', 'report_auto_evals', ['comment_hash'])


def downgrade() -> None:
    op.drop_index('ix_report_auto_eval_comment_hash', table_name='report_auto_evals')
    op.drop_index('ix_report_auto_eval_decision', table_name='report_auto_evals')
    op.drop_index('ix_report_auto_eval_decided_at', table_name='report_auto_evals')
    op.drop_index('ix_report_auto_eval_report', table_name='report_auto_evals')
    op.drop_table('report_auto_evals')
    sa.Enum(name='report_auto_decision_enum').drop(op.get_bind(), checkfirst=True)
