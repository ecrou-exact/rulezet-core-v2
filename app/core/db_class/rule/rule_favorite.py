"""rule_favorite.py — User favorites for rules."""
from datetime import datetime
from .... import db


class RuleFavoriteUser(db.Model):
    __tablename__ = 'rule_favorite_user'
    __table_args__ = (
        db.UniqueConstraint('rule_id', 'user_id', name='uq_rule_favorite'),
    )

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rule_id    = db.Column(db.Integer, db.ForeignKey('rule.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    rule = db.relationship('Rule', back_populates='favorited_by_users_assocs')
    user = db.relationship('User', foreign_keys=[user_id], lazy='joined')

    def to_json(self):
        return {
            'rule_id':    self.rule_id,
            'user_id':    self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
