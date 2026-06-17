"""format_rule.py — Detection rule formats (YARA, Sigma, Suricata, …)."""
from datetime import datetime
import uuid as _uuid
from sqlalchemy import func
from .... import db


def _gen_uuid():
    return str(_uuid.uuid4())


class FormatRule(db.Model):
    __tablename__ = 'format_rule'

    id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)

    name           = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description    = db.Column(db.Text, nullable=True)
    file_extension = db.Column(db.String(16), nullable=True)   # yar, yml, rules, zeek…
    icon           = db.Column(db.String(64), nullable=True)   # FA class e.g. fa-shield-halved
    color          = db.Column(db.String(16), nullable=True)   # hex e.g. #FF6B2B

    can_be_executed = db.Column(db.Boolean, nullable=False, default=False)
    is_builtin      = db.Column(db.Boolean, nullable=False, default=False)

    # Who created this format (null for built-in formats)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)

    creator = db.relationship('User', foreign_keys=[user_id], lazy='joined',
                              backref=db.backref('created_formats', lazy='dynamic'))

    # ── Helpers ───────────────────────────────────────────────────────────────
    def get_rule_count(self):
        from .rule import Rule
        return Rule.query.filter(
            Rule.format_id == self.id,
            Rule.is_deleted == False,
        ).count()

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_json(self):
        creator_name = None
        if self.creator:
            creator_name = f"{self.creator.first_name} {self.creator.last_name}".strip()
        return {
            'id':             self.id,
            'uuid':           self.uuid,
            'name':           self.name,
            'description':    self.description,
            'file_extension': self.file_extension,
            'icon':           self.icon,
            'color':          self.color,
            'can_be_executed': self.can_be_executed,
            'is_builtin':     self.is_builtin,
            'is_active':      self.is_active,
            'user_id':        self.user_id,
            'creator':        creator_name,
            'created_at':     self.created_at.isoformat() if self.created_at else None,
            'rule_count':     self.get_rule_count(),
        }

    def to_json_light(self):
        return {
            'id':             self.id,
            'uuid':           self.uuid,
            'name':           self.name,
            'file_extension': self.file_extension,
            'icon':           self.icon,
            'color':          self.color,
            'can_be_executed': self.can_be_executed,
            'is_builtin':     self.is_builtin,
        }
