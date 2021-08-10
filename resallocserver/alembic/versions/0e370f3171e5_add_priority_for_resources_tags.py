"""
Add priority for resources tags

Revision ID: 0e370f3171e5
Revises: 210774551cd3
Create Date: 2021-08-12 13:43:42.890692
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e370f3171e5'
down_revision = '210774551cd3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('resource_tags', schema=None) as batch_op:
        batch_op.add_column(sa.Column('priority', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('resource_tags', schema=None) as batch_op:
        batch_op.drop_column('priority')
