from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250903_add_admin_audit_logs'
down_revision = '0bb9a42874c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.create_table(
            'admin_audit_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), nullable=False, index=True),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('note', sa.String(length=255), nullable=True),
            sa.Column('actor_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        # FKs added carefully (may be cross-schema in some DBs)
        try:
            op.create_foreign_key('fk_admin_audit_logs_user', 'admin_audit_logs', 'users', ['user_id'], ['id'], ondelete='CASCADE')
            op.create_foreign_key('fk_admin_audit_logs_actor', 'admin_audit_logs', 'users', ['actor_id'], ['id'], ondelete='SET NULL')
        except Exception:
            pass
        try:
            op.create_index('ix_admin_audit_logs_user_id', 'admin_audit_logs', ['user_id'])
        except Exception:
            pass
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_table('admin_audit_logs')
    except Exception:
        pass

