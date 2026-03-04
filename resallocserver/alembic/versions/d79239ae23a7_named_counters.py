"""
Named Counters added

Revision ID: d79239ae23a7
Revises: b50e3f64fc2d
Create Date: 2026-03-04 10:52:27.756502
"""

from alembic import op
import sqlalchemy as sa

revision = 'd79239ae23a7'
down_revision = 'b50e3f64fc2d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'named_counters',
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Integer(), nullable=True),
        sa.Column('counter_name', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
        sa.PrimaryKeyConstraint('counter_name', 'value'),
        sa.UniqueConstraint('value', 'counter_name')
    )
    with op.batch_alter_table('named_counters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_named_counters_counter_name'),
                              ['counter_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_named_counters_value'), ['value'],
                              unique=False)


def downgrade():
    with op.batch_alter_table('named_counters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_named_counters_value'))
        batch_op.drop_index(batch_op.f('ix_named_counters_counter_name'))
    op.drop_table('named_counters')
