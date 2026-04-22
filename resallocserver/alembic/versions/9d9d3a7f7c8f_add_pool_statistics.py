# pylint: disable=invalid-name

"""Add pool statistics

Revision ID: 9d9d3a7f7c8f
Revises: d79239ae23a7
Create Date: 2026-04-21 11:17:44.729847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d9d3a7f7c8f'
down_revision = 'd79239ae23a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_successful_start', sa.Float(), nullable=True, default=None))
        batch_op.add_column(sa.Column('last_attempt_to_start', sa.Float(), nullable=True, default=None))
        batch_op.add_column(sa.Column('startup_success_rate', sa.Float(), nullable=True, default=None))
        batch_op.add_column(sa.Column('startup_time_avg', sa.Float(), nullable=True, default=None))


def downgrade():
    with op.batch_alter_table('pools', schema=None) as batch_op:
        batch_op.drop_column('startup_time_avg')
        batch_op.drop_column('startup_success_rate')
        batch_op.drop_column('last_attempt_to_start')
        batch_op.drop_column('last_successful_start')
