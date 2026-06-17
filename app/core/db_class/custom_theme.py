"""custom_theme.py — CustomTheme model for custom and built-in theme overrides."""
from datetime import datetime
import uuid as _uuid
import re
from ... import db


def _gen_uuid():
    return str(_uuid.uuid4())


def slugify(name):
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')[:48]


class CustomTheme(db.Model):
    __tablename__ = 'custom_theme'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid       = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    name       = db.Column(db.String(64), nullable=False)
    css_key    = db.Column(db.String(64), unique=True, nullable=False)
    icon       = db.Column(db.String(64), nullable=False, default='fa-palette')
    is_dark    = db.Column(db.Boolean, default=False, nullable=False)
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)
    is_public  = db.Column(db.Boolean, default=False, nullable=False)
    css_vars   = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)
    meta       = db.Column(db.JSON, nullable=True)

    def to_json(self):
        return {
            'id':         self.id,
            'uuid':       self.uuid,
            'name':       self.name,
            'css_key':    self.css_key,
            'icon':       self.icon,
            'is_dark':    self.is_dark,
            'is_builtin': self.is_builtin,
            'css_vars':   self.css_vars or {},
            'is_public':  self.is_public,
            'is_active':  self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
