"""rule_edit_proposal.py — Community edit proposals for rules (PR-style)."""
from datetime import datetime
import uuid as _uuid
from .... import db

PROPOSAL_STATUSES = ('pending', 'accepted', 'rejected', 'withdrawn')


def _gen_uuid():
    return str(_uuid.uuid4())


class RuleEditProposal(db.Model):
    __tablename__ = 'rule_edit_proposal'

    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid      = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    rule_id   = db.Column(db.Integer, db.ForeignKey('rule.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                          nullable=True, index=True)

    # Proposal content
    title            = db.Column(db.String(256), nullable=False)
    motivation       = db.Column(db.Text, nullable=True)
    proposed_content = db.Column(db.Text, nullable=True)      # new content being proposed
    proposed_description = db.Column(db.Text, nullable=True)

    # Snapshot of the rule at proposal creation time
    previous_content = db.Column(db.Text, nullable=True)      # rule.content before this proposal
    previous_version = db.Column(db.String(64), nullable=True) # rule.version before this proposal

    # Diff fields — only the fields being changed
    diff_fields = db.Column(db.JSON, nullable=True)  # {"title": "new", "description": "new", ...}

    status      = db.Column(db.String(16), nullable=False, default='pending', index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)

    timestamp  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rule     = db.relationship('Rule', back_populates='edit_proposals', lazy='joined')
    author   = db.relationship('User', foreign_keys=[user_id], lazy='joined')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], lazy='joined')

    def to_json_for_discuss(self):
        author_name = None
        if self.author:
            author_name = f"{self.author.first_name} {self.author.last_name}".strip()
        return {
            'id':          self.id,
            'uuid':        self.uuid,
            'rule_id':     self.rule_id,
            'title':       self.title,
            'motivation':  self.motivation,
            'status':      self.status,
            'timestamp':   self.timestamp.isoformat() if self.timestamp else None,
            'author':      author_name,
            'diff_fields': self.diff_fields or {},
        }

    def to_json(self):
        reviewer_name = None
        if self.reviewer:
            reviewer_name = f"{self.reviewer.first_name} {self.reviewer.last_name}".strip()
        d = self.to_json_for_discuss()
        d.update({
            'proposed_content':     self.proposed_content,
            'proposed_description': self.proposed_description,
            'previous_content':     self.previous_content,
            'previous_version':     self.previous_version,
            'diff_fields':          self.diff_fields or {},
            'reviewer':             reviewer_name,
            'reviewed_at':          self.reviewed_at.isoformat() if self.reviewed_at else None,
            'review_note':          self.review_note,
        })
        return d
