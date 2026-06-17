"""add: [themes] is_public column on custom_theme

Revision ID: f2a9c3d7e1b8
Revises: e4c2b8f01d5a
Create Date: 2026-06-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a9c3d7e1b8'
down_revision = 'e4c2b8f01d5a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('custom_theme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_public', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('custom_theme', schema=None) as batch_op:
        batch_op.drop_column('is_public')
