"""
allow resource reuse

Revision ID: eac9fc01d0d1
Revises: cdf29a997efc
Create Date: 2020-04-05 20:25:01.257377
"""

import time
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm.session import Session

from resallocserver import models, logic
from resalloc import helpers

# revision identifiers, used by Alembic.
revision = 'eac9fc01d0d1'
down_revision = 'cdf29a997efc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('released_at', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('releases_counter', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sandbox', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('sandboxed_since', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ticket_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_ticket_id", ['ticket_id'])
        batch_op.create_foreign_key("fk_resource_to_ticket", 'tickets', ['ticket_id'], ['id'])

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sandbox', sa.String(), nullable=True))
    bind = op.get_bind()
    session = Session(bind=bind)

    for ticket in (session.query(models.Ticket).filter(
                       models.Ticket.state == helpers.TState.OPEN)):
        ticket.sandbox = str(uuid.uuid1())
    qres = logic.QResources(session)
    for resource in qres.on():
        resource.releases_counter = 0
        for ticket in session.query(models.Ticket)\
                .filter(models.Ticket.resource_id == resource.id):
            resource.ticket_id = ticket.id
            resource.sandbox = ticket.sandbox
            resource.sandboxed_since = time.time()
    session.commit()


def downgrade():
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_constraint("fk_resource_to_ticket", type_='foreignkey')
        batch_op.drop_constraint("uq_ticket_id", type_='unique')
        batch_op.drop_column('ticket_id')
        batch_op.drop_column('sandboxed_since')
        batch_op.drop_column('sandbox')
        batch_op.drop_column('releases_counter')
        batch_op.drop_column('released_at')

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_column('sandbox')
