"""add: [comments] comment and reaction models

Revision ID: cfe8962e5198
Revises: bc8dad771541
Create Date: 2026-06-05 10:19:51.045727

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfe8962e5198'
down_revision = 'bc8dad771541'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('comment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('uuid', sa.String(length=36), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_original', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('depth', sa.Integer(), nullable=False),
        sa.Column('root_id', sa.Integer(), nullable=True),
        sa.Column('object_type', sa.String(length=64), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['comment.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
    )
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comment_created_by'), ['created_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_comment_object_id'), ['object_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comment_object_type'), ['object_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_comment_parent_id'), ['parent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comment_root_id'), ['root_id'], unique=False)

    op.create_table('comment_reaction',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reaction', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['comment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', name='uq_comment_reaction_user'),
    )
    with op.batch_alter_table('comment_reaction', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comment_reaction_comment_id'), ['comment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comment_reaction_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('comment_reaction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comment_reaction_user_id'))
        batch_op.drop_index(batch_op.f('ix_comment_reaction_comment_id'))
    op.drop_table('comment_reaction')

    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comment_root_id'))
        batch_op.drop_index(batch_op.f('ix_comment_parent_id'))
        batch_op.drop_index(batch_op.f('ix_comment_object_type'))
        batch_op.drop_index(batch_op.f('ix_comment_object_id'))
        batch_op.drop_index(batch_op.f('ix_comment_created_by'))
    op.drop_table('comment')
