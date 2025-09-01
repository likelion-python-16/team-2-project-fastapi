"""
cascade email_verifications.user_id and soft delete fields on users

Revision ID: 20250901_cascade_ev_and_soft_delete_users
Revises: 20250830_add_social_login_fields
Create Date: 2025-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '20250901_cascade_ev_and_soft_delete_users'
down_revision = '20250830_add_social_login_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) users: soft delete columns
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch.create_index('ix_users_is_deleted', ['is_deleted'])

    # 2) email_verifications.user_id ON DELETE CASCADE
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    # find existing FK name
    fk_name = None
    for fk in inspector.get_foreign_keys('email_verifications'):
        if fk.get('constrained_columns') == ['user_id'] and fk.get('referred_table') == 'users':
            fk_name = fk.get('name')
            break
    # drop old FK if exists
    if fk_name:
        op.drop_constraint(fk_name, 'email_verifications', type_='foreignkey')
    # create new FK with CASCADE
    op.create_foreign_key(
        'fk_email_verifications_user_id_users_cascade',
        'email_verifications', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    # revert FK to no action (no ondelete)
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    # drop our cascade FK if exists
    for fk in inspector.get_foreign_keys('email_verifications'):
        if fk.get('constrained_columns') == ['user_id'] and fk.get('referred_table') == 'users':
            op.drop_constraint(fk.get('name'), 'email_verifications', type_='foreignkey')
            break
    # recreate without ondelete
    op.create_foreign_key(
        'fk_email_verifications_user_id_users',
        'email_verifications', 'users', ['user_id'], ['id']
    )

    # drop soft delete columns
    with op.batch_alter_table('users') as batch:
        try:
            batch.drop_index('ix_users_is_deleted')
        except Exception:
            pass
        batch.drop_column('deleted_at')
        batch.drop_column('is_deleted')

