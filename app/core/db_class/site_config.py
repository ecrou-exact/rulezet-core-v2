from datetime import datetime
from ... import db


class SiteConfig(db.Model):
    __tablename__ = 'site_config'

    key        = db.Column(db.String(64),  primary_key=True)
    value      = db.Column(db.String(256), nullable=False, default='')
    label      = db.Column(db.String(128), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def to_json(self):
        return {
            'key':        self.key,
            'value':      self.value,
            'label':      self.label,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_site_value(key: str, default: str = '') -> str:
    cfg = SiteConfig.query.get(key)
    return cfg.value if cfg else default


def get_site_bool(key: str, default: bool = True) -> bool:
    val = get_site_value(key, '1' if default else '0')
    return val.lower() in ('1', 'true', 'yes')


def set_site_value(key: str, value: str, user_id=None) -> None:
    cfg = SiteConfig.query.get(key)
    if cfg is None:
        cfg = SiteConfig(key=key)
        db.session.add(cfg)
    cfg.value      = str(value)
    cfg.updated_by = user_id
    db.session.commit()


# ── Seeding ───────────────────────────────────────────────────────────────────

DEFAULTS = {
    'allow_registration':          ('1', 'Allow public registration'),
    'allow_login':                 ('1', 'Allow non-admin login'),
    'email_verification_enabled':  ('0', 'Require email verification for new accounts'),
    'weather_widget_enabled':      ('0', 'Show weather & local time widget in topbar'),
    'tags_enabled':                ('1', 'Enable Tags feature'),
}


def seed_site_config():
    for key, (value, label) in DEFAULTS.items():
        if SiteConfig.query.get(key) is None:
            db.session.add(SiteConfig(key=key, value=value, label=label))
    db.session.commit()
