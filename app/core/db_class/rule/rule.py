"""rule.py — Rule model: detection rules (YARA, Sigma, Suricata, etc.)."""
from datetime import datetime
import uuid as _uuid
import hashlib
from .... import db

RULE_FORMATS   = ('yara', 'sigma', 'suricata', 'zeek', 'wazuh', 'nse', 'crs', 'nova')
RULE_STATUSES  = ('stable', 'test', 'experimental', 'deprecated')
RULE_SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
RULE_CONFIDENCE = ('high', 'medium', 'low')

FORMAT_EXTENSIONS = {
    'yara':     'yar',
    'sigma':    'yml',
    'suricata': 'rules',
    'zeek':     'zeek',
    'wazuh':    'xml',
    'nse':      'nse',
    'crs':      'conf',
    'nova':     'nov',
}


def _gen_uuid():
    return str(_uuid.uuid4())


class Rule(db.Model):
    __tablename__ = 'rule'

    # ── Identity ──────────────────────────────────────────────────────────────
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid          = db.Column(db.String(36), unique=True, nullable=False,
                              default=_gen_uuid, index=True)
    original_uuid = db.Column(db.String(36), nullable=True, index=True)

    # ── Content ───────────────────────────────────────────────────────────────
    title       = db.Column(db.String(512), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    content     = db.Column(db.Text, nullable=True)           # raw rule content
    rule_hash   = db.Column(db.String(64), nullable=True, index=True)  # SHA-256 of content

    # ── Classification ────────────────────────────────────────────────────────
    format_id   = db.Column(db.Integer, db.ForeignKey('format_rule.id'), nullable=True, index=True)
    version     = db.Column(db.String(64), nullable=True)
    status      = db.Column(db.String(32), nullable=True, default='stable', index=True)
    severity    = db.Column(db.String(16), nullable=True, index=True)   # critical/high/medium/low/info
    confidence  = db.Column(db.String(16), nullable=True)               # high/medium/low
    platforms   = db.Column(db.JSON, nullable=True)                     # ["windows","linux",…]
    mitre_attack = db.Column(db.JSON, nullable=True)                    # ["T1059","T1059.001",…]
    references  = db.Column(db.JSON, nullable=True)                     # list of URLs
    false_positives = db.Column(db.Text, nullable=True)

    # ── Authorship ────────────────────────────────────────────────────────────
    author        = db.Column(db.String(256), nullable=True)  # original author string from rule
    license       = db.Column(db.String(128), nullable=True)
    source        = db.Column(db.String(256), nullable=True)  # origin (GitHub repo, feed name…)
    github_path   = db.Column(db.String(512), nullable=True)
    creation_date = db.Column(db.DateTime, nullable=True, index=True)
    last_modif    = db.Column(db.DateTime, nullable=True, index=True)

    # ── Submitter (who imported the rule on this platform) ───────────────────
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)

    # ── Community ─────────────────────────────────────────────────────────────
    vote_up    = db.Column(db.Integer, nullable=False, default=0)
    vote_down  = db.Column(db.Integer, nullable=False, default=0)
    is_public  = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False, index=True)

    # ── Connector origin ──────────────────────────────────────────────────────
    connector_id      = db.Column(db.Integer,
                                  db.ForeignKey('connector.id', ondelete='SET NULL'),
                                  nullable=True, index=True)
    remote_rule_uuid  = db.Column(db.String(36), nullable=True, index=True)
    sync_instance_url = db.Column(db.String(255), nullable=True)

    # ── Soft delete ───────────────────────────────────────────────────────────
    is_deleted        = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at        = db.Column(db.DateTime, nullable=True)
    deleted_by_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    delete_batch_uuid = db.Column(db.String(36), nullable=True, index=True)

    # ── Standard timestamps ───────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────────────────────
    submitter = db.relationship('User', foreign_keys=[user_id], lazy='joined',
                                primaryjoin='Rule.user_id == User.id')
    deleter   = db.relationship('User', foreign_keys=[deleted_by_id], lazy='select',
                                primaryjoin='Rule.deleted_by_id == User.id')

    format_rule = db.relationship('FormatRule', foreign_keys=[format_id], lazy='joined')

    rule_tags_assocs         = db.relationship('RuleTag', back_populates='rule',
                                               cascade='all, delete-orphan', lazy='dynamic')
    cve_records              = db.relationship('RuleCVE', back_populates='rule',
                                               cascade='all, delete-orphan', lazy='dynamic')
    favorited_by_users_assocs = db.relationship('RuleFavoriteUser', back_populates='rule',
                                                cascade='all, delete-orphan', lazy='dynamic')
    edit_proposals           = db.relationship('RuleEditProposal', back_populates='rule',
                                               cascade='all, delete-orphan', lazy='dynamic')
    version_history          = db.relationship('RuleHistory', back_populates='rule',
                                               cascade='all, delete-orphan', lazy='dynamic',
                                               order_by='RuleHistory.version_num.desc()')

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def format(self):
        """Convenience accessor — returns the format name string (or None)."""
        return self.format_rule.name if self.format_rule else None

    @property
    def format_uuid(self):
        return self.format_rule.uuid if self.format_rule else None

    def compute_hash(self):
        if self.content:
            self.rule_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        else:
            self.rule_hash = None
        return self.rule_hash

    def get_extension(self):
        if self.format_rule and self.format_rule.file_extension:
            return self.format_rule.file_extension
        return FORMAT_EXTENSIONS.get((self.format or '').lower(), 'txt')

    def get_submitter_name(self):
        if self.submitter:
            return f"{self.submitter.first_name} {self.submitter.last_name}".strip()
        return None

    def get_submitter_avatar(self):
        if self.submitter and hasattr(self.submitter, 'get_avatar_url'):
            return self.submitter.get_avatar_url()
        return None

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_json(self):
        from flask_login import current_user
        from .rule_favorite import RuleFavoriteUser

        is_favorited = False
        if current_user.is_authenticated and not current_user.is_anonymous:
            is_favorited = RuleFavoriteUser.query.filter_by(
                user_id=current_user.id, rule_id=self.id
            ).first() is not None

        return {
            'id':              self.id,
            'uuid':            self.uuid,
            'original_uuid':   self.original_uuid,
            'title':           self.title,
            'description':     self.description,
            'format_id':       self.format_id,
            'format_uuid':     self.format_uuid,
            'format':          self.format,
            'version':         self.version,
            'status':          self.status,
            'severity':        self.severity,
            'confidence':      self.confidence,
            'platforms':       self.platforms or [],
            'mitre_attack':    self.mitre_attack or [],
            'references':      self.references or [],
            'false_positives': self.false_positives,
            'license':         self.license,
            'author':          self.author,
            'source':          self.source,
            'github_path':     self.github_path,
            'creation_date':   self.creation_date.strftime('%Y-%m-%d %H:%M') if self.creation_date else None,
            'last_modif':      self.last_modif.strftime('%Y-%m-%d %H:%M') if self.last_modif else None,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
            'vote_up':         self.vote_up,
            'vote_down':       self.vote_down,
            'user_id':         self.user_id,
            'is_public':       self.is_public,
            'is_verified':     self.is_verified,
            'content':         self.content,
            'rule_hash':       self.rule_hash,
            'is_favorited':    is_favorited,
            'submitter':       self.get_submitter_name(),
            'submitter_avatar': self.get_submitter_avatar(),
            'sync_instance_url': self.sync_instance_url,
        }

    def to_json_detail(self):
        from flask_login import current_user
        from .rule_favorite import RuleFavoriteUser
        from ....core.db_class.comment import Comment

        total_votes = (self.vote_up or 0) + (self.vote_down or 0)
        vote_ratio  = round((self.vote_up or 0) / total_votes * 100) if total_votes > 0 else 0

        favorites_count = self.favorited_by_users_assocs.count()

        is_favorited = False
        if current_user.is_authenticated and not current_user.is_anonymous:
            is_favorited = RuleFavoriteUser.query.filter_by(
                user_id=current_user.id, rule_id=self.id
            ).first() is not None

        submitter_info = None
        if self.submitter:
            submitter_info = {
                'id':       self.submitter.id,
                'username': self.get_submitter_name(),
            }

        tags = [assoc.to_json() for assoc in self.rule_tags_assocs]

        cves = [c.to_json() for c in self.cve_records]

        comments = Comment.query.filter_by(
            object_type='rule', object_id=self.id, is_active=True
        ).order_by(Comment.created_at.desc()).limit(20).all()

        proposals = self.edit_proposals.order_by(
            # RuleEditProposal.timestamp.desc()  — imported dynamically to avoid circular
        ).limit(10).all()
        proposals_summary = [p.to_json_for_discuss() for p in proposals]

        return {
            'identity': {
                'id':            self.id,
                'uuid':          self.uuid,
                'original_uuid': self.original_uuid,
                'title':         self.title,
                'version':       self.version,
                'format_id':     self.format_id,
                'format_uuid':   self.format_uuid,
                'format':        self.format,
                'format_detail': self.format_rule.to_json_light() if self.format_rule else None,
                'status':        self.status,
                'rule_hash':     self.rule_hash,
            },
            'content': {
                'content':         self.content,
                'description':     self.description,
                'false_positives': self.false_positives,
                'source':          self.source,
                'github_path':     self.github_path,
                'extension':       self.get_extension(),
            },
            'authorship': {
                'author':        self.author,
                'license':       self.license,
                'creation_date': self.creation_date.strftime('%Y-%m-%d %H:%M') if self.creation_date else None,
                'last_modif':    self.last_modif.strftime('%Y-%m-%d %H:%M') if self.last_modif else None,
                'submitter':     submitter_info,
            },
            'classification': {
                'severity':    self.severity,
                'confidence':  self.confidence,
                'platforms':   self.platforms or [],
                'mitre_attack': self.mitre_attack or [],
                'references':  self.references or [],
            },
            'community': {
                'votes': {
                    'up':            self.vote_up or 0,
                    'down':          self.vote_down or 0,
                    'total':         total_votes,
                    'ratio_percent': vote_ratio,
                },
                'favorites': {
                    'count':        favorites_count,
                    'is_favorited': is_favorited,
                },
                'comments': {
                    'count':  Comment.query.filter_by(
                                  object_type='rule', object_id=self.id, is_active=True
                              ).count(),
                    'latest': [c.to_json() for c in comments],
                },
                'is_verified': self.is_verified,
            },
            'relations': {
                'tags': tags,
                'cves': cves,
            },
            'history': {
                'edit_proposals': {
                    'count':  self.edit_proposals.count(),
                    'latest': proposals_summary,
                },
                'versions': {
                    'count':  self.version_history.count(),
                    'latest': [h.to_json() for h in self.version_history.limit(10)],
                },
            },
            'connector': {
                'connector_id':      self.connector_id,
                'remote_rule_uuid':  self.remote_rule_uuid,
                'sync_instance_url': self.sync_instance_url,
            },
        }
