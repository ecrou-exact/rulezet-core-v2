"""add: [jobs] background job table

Revision ID: a1b2c3d4e5f6
Revises: f2a9c3d7e1b8
Create Date: 2026-06-05 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'f2a9c3d7e1b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'job',
        sa.Column('id',          sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column('uuid',        sa.String(36),    unique=True, nullable=False),
        sa.Column('type',        sa.String(64),    nullable=False),
        sa.Column('title',       sa.String(128),   nullable=False),
        sa.Column('status',      sa.String(16),    nullable=False, server_default='pending'),
        sa.Column('progress',    sa.Integer(),     nullable=False, server_default='0'),
        sa.Column('logs',        sa.JSON(),        nullable=True),
        sa.Column('result',      sa.JSON(),        nullable=True),
        sa.Column('error',       sa.Text(),        nullable=True),
        sa.Column('started_at',  sa.DateTime(),    nullable=True),
        sa.Column('finished_at', sa.DateTime(),    nullable=True),
        sa.Column('created_at',  sa.DateTime(),    nullable=False),
        sa.Column('updated_at',  sa.DateTime(),    nullable=True),
        sa.Column('created_by',  sa.Integer(),     sa.ForeignKey('user.id'), nullable=True),
        sa.Column('is_active',   sa.Boolean(),     nullable=False, server_default='1'),
        sa.Column('deleted_at',  sa.DateTime(),    nullable=True),
        sa.Column('deleted_by',  sa.Integer(),     nullable=True),
        sa.Column('meta',        sa.JSON(),        nullable=True),
    )


def downgrade():
    op.drop_table('job')
