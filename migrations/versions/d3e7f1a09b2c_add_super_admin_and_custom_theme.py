"""add: [themes] super_admin flag on user + custom_theme table

Revision ID: d3e7f1a09b2c
Revises: cfe8962e5198
Create Date: 2026-06-05 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e7f1a09b2c'
down_revision = 'cfe8962e5198'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('super_admin', sa.Boolean(), nullable=False, server_default='0'))

    op.create_table('custom_theme',
        sa.Column('id',         sa.Integer(),     autoincrement=True, nullable=False),
        sa.Column('uuid',       sa.String(36),    nullable=False),
        sa.Column('name',       sa.String(64),    nullable=False),
        sa.Column('css_key',    sa.String(64),    nullable=False),
        sa.Column('icon',       sa.String(64),    nullable=False),
        sa.Column('is_dark',    sa.Boolean(),     nullable=False),
        sa.Column('is_builtin', sa.Boolean(),     nullable=False),
        sa.Column('css_vars',   sa.JSON(),        nullable=True),
        sa.Column('created_at', sa.DateTime(),    nullable=False),
        sa.Column('updated_at', sa.DateTime(),    nullable=True),
        sa.Column('created_by', sa.Integer(),     nullable=True),
        sa.Column('is_active',  sa.Boolean(),     nullable=False),
        sa.Column('deleted_at', sa.DateTime(),    nullable=True),
        sa.Column('deleted_by', sa.Integer(),     nullable=True),
        sa.Column('meta',       sa.JSON(),        nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
        sa.UniqueConstraint('css_key'),
    )


def downgrade():
    op.drop_table('custom_theme')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('super_admin')
