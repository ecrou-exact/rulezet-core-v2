"""chg: [themes] drop super_admin column — admin role is sufficient

Revision ID: e4c2b8f01d5a
Revises: d3e7f1a09b2c
Create Date: 2026-06-05 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4c2b8f01d5a'
down_revision = 'd3e7f1a09b2c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('super_admin')


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('super_admin', sa.Boolean(), nullable=False, server_default='0'))
