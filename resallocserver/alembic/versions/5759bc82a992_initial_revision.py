"""Initial revision

Revision ID: 5759bc82a992
Revises: 
Create Date: 2017-09-20 09:11:54.520899

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5759bc82a992'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pools',
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('last_start', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('resources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('user', sa.String(), nullable=True),
    sa.Column('data', sa.LargeBinary(), nullable=True),
    sa.Column('pool', sa.String(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('check_last_time', sa.Float(), nullable=True),
    sa.Column('check_failed_count', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resource_tags',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
    sa.PrimaryKeyConstraint('id', 'resource_id')
    )
    op.create_table('tickets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=True),
    sa.Column('state', sa.String(), nullable=True),
    sa.Column('tid', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ticket_tags',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id', 'ticket_id')
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_table('ticket_tags')
    op.drop_table('tickets')
    op.drop_table('resource_tags')
    op.drop_table('resources')
    op.drop_table('pools')
