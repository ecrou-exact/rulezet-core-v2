"""
comment.py — Comment and CommentReaction models.
"""
from datetime import datetime
import uuid as _uuid
from ... import db


def _gen_uuid():
    return str(_uuid.uuid4())


class Comment(db.Model):
    __tablename__ = 'comment'

    # ── Core ─────────────────────────────────────────────────────────────────
    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid             = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    content          = db.Column(db.Text, nullable=False)
    content_original = db.Column(db.Text, nullable=True)

    # ── Thread structure ──────────────────────────────────────────────────────
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='SET NULL'),
                          nullable=True, index=True)
    depth     = db.Column(db.Integer, default=0, nullable=False)
    root_id   = db.Column(db.Integer, nullable=True, index=True)

    # ── Polymorphic target ────────────────────────────────────────────────────
    object_type = db.Column(db.String(64), nullable=False, index=True)
    object_id   = db.Column(db.Integer,    nullable=False, index=True)

    # ── Visibility ────────────────────────────────────────────────────────────
    is_public = db.Column(db.Boolean, default=True,  nullable=False)

    # ── Standard fields ───────────────────────────────────────────────────────
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at  = db.Column(db.DateTime, nullable=True)
    deleted_by  = db.Column(db.Integer, nullable=True)
    meta        = db.Column(db.JSON, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    author = db.relationship(
        'User',
        foreign_keys=[created_by],
        lazy='joined',
        primaryjoin='Comment.created_by == User.id',
    )
    reactions = db.relationship(
        'CommentReaction',
        backref='comment',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    # ── Computed properties ───────────────────────────────────────────────────
    @property
    def reply_count(self):
        return Comment.query.filter_by(parent_id=self.id, is_active=True).count()

    @property
    def like_count(self):
        return self.reactions.filter_by(reaction='like').count()

    @property
    def dislike_count(self):
        return self.reactions.filter_by(reaction='dislike').count()

    def to_json(self, current_user_id=None, show_original=False):
        author = self.author
        if author:
            author_dict = {
                'id':       author.id,
                'name':     author.display_name(),
                'avatar':   author.avatar_filename,
                'initials': author.initials(),
                'handle':   author.username,
            }
        else:
            author_dict = {
                'id':       None,
                'name':     'Deleted user',
                'avatar':   None,
                'initials': '?',
                'handle':   None,
            }

        # Determine user's own reaction
        user_reaction = None
        if current_user_id:
            rxn = self.reactions.filter_by(user_id=current_user_id).first()
            if rxn:
                user_reaction = rxn.reaction

        content_display = self.content
        if show_original and self.content_original:
            content_display = self.content_original

        return {
            'id':               self.id,
            'uuid':             self.uuid,
            'content':          content_display,
            'parent_id':        self.parent_id,
            'depth':            self.depth,
            'root_id':          self.root_id,
            'object_type':      self.object_type,
            'object_id':        self.object_id,
            'is_public':        self.is_public,
            'created_at':       self.created_at.isoformat() if self.created_at else None,
            'updated_at':       self.updated_at.isoformat() if self.updated_at else None,
            'created_by':       self.created_by,
            'is_active':        self.is_active,
            'is_deleted':       not self.is_active,
            'deleted_at':       self.deleted_at.isoformat() if self.deleted_at else None,
            'reply_count':      self.reply_count,
            'like_count':       self.like_count,
            'dislike_count':    self.dislike_count,
            'user_reaction':    user_reaction,
            'author':           author_dict,
            'is_admin':          author.is_admin() if author else False,
        }


class CommentReaction(db.Model):
    __tablename__ = 'comment_reaction'
    __table_args__ = (
        db.UniqueConstraint('comment_id', 'user_id', name='uq_comment_reaction_user'),
    )

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    reaction   = db.Column(db.String(16), nullable=False)   # 'like' | 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
