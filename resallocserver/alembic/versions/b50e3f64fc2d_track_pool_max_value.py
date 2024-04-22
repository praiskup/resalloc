"""
Track Pool max value
"""

from alembic import op
import sqlalchemy as sa

revision = 'b50e3f64fc2d'
down_revision = '78237445aff8'

def upgrade():
    with op.batch_alter_table('pools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('pools', schema=None) as batch_op:
        batch_op.drop_column('max')
