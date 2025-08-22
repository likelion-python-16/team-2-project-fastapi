from alembic import op
import sqlalchemy as sa

# revision identifiers are already set by Alembic when this file was created.
def upgrade():
    op.add_column('challenges', sa.Column('default_map_url', sa.String(512), nullable=True))
    op.add_column('challenges', sa.Column('default_latitude', sa.Float(), nullable=True))
    op.add_column('challenges', sa.Column('default_longitude', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('challenges', 'default_longitude')
    op.drop_column('challenges', 'default_latitude')
    op.drop_column('challenges', 'default_map_url')
