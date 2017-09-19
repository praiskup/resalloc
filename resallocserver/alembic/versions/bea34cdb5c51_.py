"""Drop name in tickets table

Revision ID: bea34cdb5c51
Revises: 5ee77b680c30
Create Date: 2017-09-19 12:14:17.273380

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bea34cdb5c51'
down_revision = '5ee77b680c30'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('tickets', 'name')


def downgrade():
    op.add_column('tickets', sa.Column('name', sa.VARCHAR(), nullable=True))
