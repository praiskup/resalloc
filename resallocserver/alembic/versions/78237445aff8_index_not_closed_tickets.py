"""
Index not-closed tickets

This is good for the `resalloc-maint ticket-list` feature.

Revision ID: 78237445aff8
Revises: a53d2303943a
Create Date: 2022-09-21 14:50:57.688708
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '78237445aff8'
down_revision = 'a53d2303943a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(
            'ix_not_closed_tickets', ['state'],
            unique=False,
            postgresql_where=sa.text("state != 'CLOSED'"),
        )

def downgrade():
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(
            'ix_not_closed_tickets',
            postgresql_where=sa.text("state != 'CLOSED'"),
        )
