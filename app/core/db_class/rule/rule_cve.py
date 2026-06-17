"""rule_cve.py — Structured CVE records linked to rules."""
from datetime import datetime
from .... import db


class RuleCVE(db.Model):
    __tablename__ = 'rule_cve'
    __table_args__ = (
        db.UniqueConstraint('rule_id', 'cve_id', name='uq_rule_cve'),
    )

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rule_id      = db.Column(db.Integer, db.ForeignKey('rule.id', ondelete='CASCADE'),
                             nullable=False, index=True)

    cve_id       = db.Column(db.String(32), nullable=False, index=True)  # CVE-YYYY-NNNNN
    description  = db.Column(db.Text, nullable=True)
    cvss_score   = db.Column(db.Float, nullable=True)        # 0.0 – 10.0
    cvss_vector  = db.Column(db.String(128), nullable=True)  # e.g. CVSS:3.1/AV:N/...
    severity     = db.Column(db.String(16), nullable=True)   # critical/high/medium/low/none
    published_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    rule = db.relationship('Rule', back_populates='cve_records', lazy='joined')

    def to_json(self):
        return {
            'id':           self.id,
            'rule_id':      self.rule_id,
            'cve_id':       self.cve_id,
            'description':  self.description,
            'cvss_score':   self.cvss_score,
            'cvss_vector':  self.cvss_vector,
            'severity':     self.severity,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }
