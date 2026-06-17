"""
tag.py — Tag model (custom, taxonomy, galaxy, vulnerability).
"""
from datetime import datetime
import uuid as _uuid
from ... import db


def _gen_uuid():
    return str(_uuid.uuid4())


class Tag(db.Model):
    __tablename__ = 'tag'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid        = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)

    # Full machine-readable tag name: "tlp:red", "misp-galaxy:actor=\"APT28\""
    name        = db.Column(db.String(512), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    color       = db.Column(db.String(16), nullable=True)   # hex e.g. #FF2B2B
    icon        = db.Column(db.String(128), nullable=True)  # FA class e.g. fa-tag

    # Source classification
    source      = db.Column(db.String(32), nullable=False, default='custom', index=True)
    # custom | taxonomy | galaxy | vulnerability

    namespace   = db.Column(db.String(128), nullable=True, index=True)  # e.g. 'tlp', 'actor'
    external_id = db.Column(db.String(256), nullable=True)  # MISP uuid

    is_public   = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Standard fields
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at  = db.Column(db.DateTime, nullable=True)
    deleted_by  = db.Column(db.Integer, nullable=True)
    meta        = db.Column(db.JSON, nullable=True)

    creator = db.relationship('User', foreign_keys=[created_by], lazy='joined',
                              primaryjoin='Tag.created_by == User.id')

    def to_json(self, viewer_id=None, is_admin=False):
        creator_name = None
        if self.creator:
            creator_name = f"{self.creator.first_name} {self.creator.last_name}".strip()
        return {
            'id':           self.id,
            'uuid':         self.uuid,
            'name':         self.name,
            'description':  self.description,
            'color':        self.color or '#6c757d',
            'icon':         self.icon,
            'source':       self.source,
            'namespace':    self.namespace,
            'external_id':  self.external_id,
            'is_public':    self.is_public,
            'is_active':    self.is_active,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'created_by':   self.created_by,
            'creator_name': creator_name,
            'meta':         self.meta or {},
        }
