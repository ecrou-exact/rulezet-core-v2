"""rule_tag.py — Many-to-many association between Rule and Tag."""
from datetime import datetime
from .... import db


class RuleTag(db.Model):
    __tablename__ = 'rule_tag'
    __table_args__ = (
        db.UniqueConstraint('rule_id', 'tag_id', name='uq_rule_tag'),
    )

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rule_id    = db.Column(db.Integer, db.ForeignKey('rule.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    tag_id     = db.Column(db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    tag  = db.relationship('Tag',  lazy='joined')
    rule = db.relationship('Rule', back_populates='rule_tags_assocs', lazy='joined')

    def to_json(self):
        return self.tag.to_json() if self.tag else {}
