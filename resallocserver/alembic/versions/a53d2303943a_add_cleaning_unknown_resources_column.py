"""Add cleaning_unknown_resources column

Revision ID: a53d2303943a
Revises: 0e370f3171e5
Create Date: 2022-06-05 14:20:16.089579

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a53d2303943a'
down_revision = '0e370f3171e5'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Otherwise SQLite cannot add a column with non-constant default
    kwargs = {"recreate": "always"} if bind.engine.name == "sqlite" else {}

    with op.batch_alter_table('pools', schema=None, **kwargs) as batch_op:
        batch_op.add_column(sa.Column(
            'cleaning_unknown_resources',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True
        ))


def downgrade():
    with op.batch_alter_table('pools', schema=None) as batch_op:
        batch_op.drop_column('cleaning_unknown_resources')
