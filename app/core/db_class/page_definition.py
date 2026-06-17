"""page_definition.py — Dynamic page model for the Template Studio."""
from datetime import datetime
import uuid as _uuid
from ... import db


def _gen_uuid():
    return str(_uuid.uuid4())


class PageDefinition(db.Model):
    __tablename__ = 'page_definition'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid                = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    name                = db.Column(db.String(128), nullable=False)
    description         = db.Column(db.Text, nullable=True)
    slug                = db.Column(db.String(128), unique=True, nullable=False)

    # Navigation integration
    nav_group           = db.Column(db.String(64), nullable=True)   # 'Navigation' | 'Admin' | 'Community' | None
    nav_label           = db.Column(db.String(128), nullable=True)
    nav_icon            = db.Column(db.String(64), nullable=True, default='fa-file')

    # Access control — same values as require_permission(): None | 'admin_only' | perm key
    required_permission = db.Column(db.String(64), nullable=True)

    # Content — ordered array of section definitions
    sections            = db.Column(db.JSON, nullable=False, default=list)

    is_published        = db.Column(db.Boolean, default=False, nullable=False)
    is_active           = db.Column(db.Boolean, default=True, nullable=False)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    deleted_at          = db.Column(db.DateTime, nullable=True)
    deleted_by          = db.Column(db.Integer, nullable=True)
    meta                = db.Column(db.JSON, nullable=True)

    def to_json(self):
        return {
            'id':                   self.id,
            'uuid':                 self.uuid,
            'name':                 self.name,
            'description':          self.description or '',
            'slug':                 self.slug,
            'nav_group':            self.nav_group,
            'nav_label':            self.nav_label,
            'nav_icon':             self.nav_icon,
            'required_permission':  self.required_permission,
            'sections':             self.sections or [],
            'is_published':         self.is_published,
            'is_active':            self.is_active,
            'created_at':           self.created_at.isoformat() if self.created_at else None,
            'updated_at':           self.updated_at.isoformat() if self.updated_at else None,
            'created_by':           self.created_by,
        }
