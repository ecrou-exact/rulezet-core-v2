"""rule_history.py — Immutable version history for rules."""
from datetime import datetime
import hashlib
from .... import db

HISTORY_CHANGE_TYPES = (
    'import',        # first import
    'edit',          # manual edit
    'proposal',      # accepted edit proposal
    'sync',          # connector sync update
    'restore',       # restored from soft delete
    'bulk_import',   # bulk import job
)


class RuleHistory(db.Model):
    """One row per version snapshot — written on every content change, never updated."""
    __tablename__ = 'rule_history'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rule_id     = db.Column(db.Integer, db.ForeignKey('rule.id', ondelete='CASCADE'),
                            nullable=False, index=True)

    # Version at the time of this snapshot
    version     = db.Column(db.String(64), nullable=True)
    version_num = db.Column(db.Integer, nullable=False, default=1, index=True)

    # The previous content before this change (what was replaced)
    previous_content = db.Column(db.Text, nullable=True)
    previous_version = db.Column(db.String(64), nullable=True)

    # The content at this snapshot
    content      = db.Column(db.Text, nullable=True)
    content_hash = db.Column(db.String(64), nullable=True)  # SHA-256 of content

    # Metadata of the rule at this snapshot (title, description, severity…)
    snapshot = db.Column(db.JSON, nullable=True)

    # What caused this history entry
    change_type    = db.Column(db.String(32), nullable=False, default='edit', index=True)
    change_summary = db.Column(db.String(512), nullable=True)

    # Who / when
    changed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Link to the proposal that triggered this entry (if change_type == 'proposal')
    proposal_id = db.Column(db.Integer,
                            db.ForeignKey('rule_edit_proposal.id', ondelete='SET NULL'),
                            nullable=True, index=True)

    rule     = db.relationship('Rule', back_populates='version_history', lazy='joined')
    editor   = db.relationship('User', foreign_keys=[changed_by], lazy='joined')
    proposal = db.relationship('RuleEditProposal', foreign_keys=[proposal_id], lazy='joined')

    @staticmethod
    def _hash(content):
        if content:
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        return None

    @classmethod
    def record(cls, rule, change_type='edit', change_summary=None,
               changed_by=None, proposal_id=None):
        """
        Create a history snapshot from the rule's CURRENT state.
        Call this AFTER updating rule fields but BEFORE committing,
        or pass the old content explicitly via previous_content.
        """
        last = cls.query.filter_by(rule_id=rule.id).order_by(
            cls.version_num.desc()
        ).first()
        version_num = (last.version_num + 1) if last else 1

        entry = cls(
            rule_id          = rule.id,
            version          = rule.version,
            version_num      = version_num,
            previous_content = last.content if last else None,
            previous_version = last.version if last else None,
            content          = rule.content,
            content_hash     = cls._hash(rule.content),
            change_type      = change_type,
            change_summary   = change_summary,
            changed_by       = changed_by,
            proposal_id      = proposal_id,
            snapshot={
                'title':        rule.title,
                'description':  rule.description,
                'format_id':    rule.format_id,
                'format':       rule.format,
                'severity':     rule.severity,
                'status':       rule.status,
                'author':       rule.author,
                'version':      rule.version,
                'platforms':    rule.platforms,
                'mitre_attack': rule.mitre_attack,
            },
        )
        return entry

    def to_json(self):
        editor_name = None
        if self.editor:
            editor_name = f"{self.editor.first_name} {self.editor.last_name}".strip()
        return {
            'id':               self.id,
            'rule_id':          self.rule_id,
            'version':          self.version,
            'version_num':      self.version_num,
            'previous_version': self.previous_version,
            'content':          self.content,
            'content_hash':     self.content_hash,
            'previous_content': self.previous_content,
            'change_type':      self.change_type,
            'change_summary':   self.change_summary,
            'changed_by':       self.changed_by,
            'editor':           editor_name,
            'changed_at':       self.changed_at.isoformat() if self.changed_at else None,
            'proposal_id':      self.proposal_id,
            'snapshot':         self.snapshot or {},
        }
