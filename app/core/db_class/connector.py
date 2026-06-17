"""connector.py — Connector model (remote instance links)."""
from datetime import datetime
import uuid as _uuid
from ... import db

CONNECTOR_DIRECTIONS = ('pull', 'push', 'bidirectional')
CONNECTOR_STATUSES   = ('unknown', 'online', 'offline', 'error')


def _gen_uuid():
    return str(_uuid.uuid4())


class Connector(db.Model):
    __tablename__ = 'connector'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid         = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    name         = db.Column(db.String(128), nullable=False)
    description  = db.Column(db.Text, nullable=True)

    url          = db.Column(db.String(512), nullable=False)
    outgoing_key = db.Column(db.String(256), nullable=True)   # key we send to remote
    incoming_key = db.Column(db.String(64), unique=True, nullable=False, default=_gen_uuid)  # remote sends this to push to us

    direction    = db.Column(db.String(16), nullable=False, default='pull')   # pull|push|bidirectional
    sync_tags    = db.Column(db.Boolean, default=True, nullable=False)

    status        = db.Column(db.String(16), nullable=False, default='unknown')
    last_check_at = db.Column(db.DateTime, nullable=True)
    last_sync_at  = db.Column(db.DateTime, nullable=True)

    # Standard fields
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)
    meta       = db.Column(db.JSON, nullable=True)

    creator = db.relationship('User', foreign_keys=[created_by], lazy='joined',
                              primaryjoin='Connector.created_by == User.id')

    def to_json(self, include_key=False):
        creator_name = None
        if self.creator:
            creator_name = f"{self.creator.first_name} {self.creator.last_name}".strip()
        return {
            'id':              self.id,
            'uuid':            self.uuid,
            'name':            self.name,
            'description':     self.description,
            'url':             self.url,
            'has_outgoing_key': bool(self.outgoing_key),
            'outgoing_key':    self.outgoing_key if include_key else None,
            'incoming_key':    self.incoming_key,
            'direction':       self.direction,
            'sync_tags':       self.sync_tags,
            'status':          self.status,
            'last_check_at':   self.last_check_at.isoformat() if self.last_check_at else None,
            'last_sync_at':    self.last_sync_at.isoformat() if self.last_sync_at else None,
            'is_active':       self.is_active,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
            'created_by':      self.created_by,
            'creator_name':    creator_name,
            'meta':            self.meta or {},
        }
