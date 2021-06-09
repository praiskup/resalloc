"""performance/indexes

Revision ID: 210774551cd3
Revises: eac9fc01d0d1
Create Date: 2021-06-06 16:45:01.691802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '210774551cd3'
down_revision = 'eac9fc01d0d1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('resource_tags', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resource_tags_resource_id'), ['resource_id'], unique=False)

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resources_pool'), ['pool'], unique=False)
        batch_op.create_index(batch_op.f('ix_resources_state'), ['state'], unique=False)
        batch_op.create_index('ix_not_ended_resources', ['state'], unique=False,
                              postgresql_where=sa.text("state != 'ENDED'"))

    with op.batch_alter_table('ticket_tags', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ticket_tags_ticket_id'), ['ticket_id'], unique=False)

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tickets_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tickets_state'), ['state'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tickets_state'))
        batch_op.drop_index(batch_op.f('ix_tickets_resource_id'))

    with op.batch_alter_table('ticket_tags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ticket_tags_ticket_id'))

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resources_state'))
        batch_op.drop_index(batch_op.f('ix_resources_pool'))
        batch_op.drop_index('ix_not_ended_resources')

    with op.batch_alter_table('resource_tags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resource_tags_resource_id'))

    # ### end Alembic commands ###