import uuid as _uuid
from datetime import datetime
from ... import db

CATEGORIES = ('user', 'system', 'security', 'admin', 'api')
LEVELS     = ('info', 'success', 'warning', 'error')


class Log(db.Model):
    __tablename__ = 'log'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid        = db.Column(db.String(36), unique=True, nullable=False,
                            default=lambda: str(_uuid.uuid4()))

    # Content
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_public   = db.Column(db.Boolean, default=False)

    # Classification
    category    = db.Column(db.String(32), nullable=False, default='system', index=True)
    action      = db.Column(db.String(64), nullable=False, index=True)
    level       = db.Column(db.String(16), nullable=False, default='info', index=True)

    # Target object (optional)
    object_type = db.Column(db.String(64), nullable=True)
    object_id   = db.Column(db.String(36), nullable=True)

    # Actor
    actor_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    ip_address  = db.Column(db.String(45), nullable=True)
    user_agent  = db.Column(db.String(256), nullable=True)

    # Extra data
    meta        = db.Column(db.JSON, nullable=True)

    # Timestamps
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)

    def to_json(self):
        from ..db_class.user import User
        actor = User.query.get(self.actor_id) if self.actor_id else None
        actor_name = None
        if actor:
            name = f"{actor.first_name or ''} {actor.last_name or ''}".strip()
            actor_name = name if name else actor.email
        return {
            'id':           self.id,
            'uuid':         self.uuid,
            'title':        self.title,
            'description':  self.description,
            'is_public':    self.is_public,
            'category':     self.category,
            'action':       self.action,
            'level':        self.level,
            'object_type':  self.object_type,
            'object_id':    self.object_id,
            'actor_id':     self.actor_id,
            'actor_name':   actor_name,
            'actor_avatar': actor.avatar_filename if actor else None,
            'ip_address':   self.ip_address,
            'user_agent':   self.user_agent,
            'meta':         self.meta,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }
