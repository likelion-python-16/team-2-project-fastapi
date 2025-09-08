"""create email verifications table

Revision ID: email_verifications
Revises: f6fcb2a96ef7
Create Date: 2025-09-02 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'email_verifications'
down_revision: Union[str, Sequence[str], None] = 'f6fcb2a96ef7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with idempotent guards."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Create table if it does not exist
    if not inspector.has_table('email_verifications'):
        op.create_table(
            'email_verifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(length=128), nullable=False),
            sa.Column('sent_to', sa.String(length=120), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # Create indexes if missing
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('email_verifications')}
    if 'ix_email_verifications_token' not in existing_indexes:
        op.create_index(op.f('ix_email_verifications_token'), 'email_verifications', ['token'], unique=True)
    if 'ix_email_verifications_user_id' not in existing_indexes:
        op.create_index(op.f('ix_email_verifications_user_id'), 'email_verifications', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema with guards (no-op if missing).
    - Drop the table directly; dropping indexes beforehand can fail on MySQL
      if the index participates in a foreign key constraint.
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table('email_verifications'):
        op.drop_table('email_verifications')
