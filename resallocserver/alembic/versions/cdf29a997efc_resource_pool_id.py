"""
resource-pool-id

Revision ID: cdf29a997efc
Revises: 5759bc82a992
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cdf29a997efc'
down_revision = '5759bc82a992'

def upgrade():
    op.create_table('ids_within_pool',
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('pool_name', sa.String(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['pool_name'], ['pools.name'], ),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
    sa.PrimaryKeyConstraint('resource_id'),
    sa.UniqueConstraint('id', 'pool_name')
    )

def downgrade():
    op.drop_table('ids_within_pool')
