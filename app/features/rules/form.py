"""
form.py — WTForms for the rules feature.

Used by the API layer for server-side validation.
The Vue front-end submits JSON; the API instantiates these forms to reuse
all validator logic without duplicating it.
"""
import re
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField,
    BooleanField, HiddenField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Optional, Length, ValidationError,
)
from flask_login import current_user


# ── Constants matching the Rule model ────────────────────────────────────────

STATUSES    = ['stable', 'test', 'experimental', 'deprecated']
SEVERITIES  = ['critical', 'high', 'medium', 'low', 'info']
CONFIDENCES = ['high', 'medium', 'low']

PLATFORMS = [
    'windows', 'linux', 'macos', 'network', 'cloud',
    'android', 'ios', 'container', 'office365', 'azure-ad',
]

# Supported vulnerability ID patterns
_CVE_PATTERN = re.compile(
    r"^("
    r"CVE[-\s]?\d{4}[-\s]?\d{4,7}"           # CVE-2024-1234
    r"|GCVE-\d+-\d{4}-\d+"                    # GCVE-0-2024-1234
    r"|GHSA-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}"  # GHSA-xxxx-xxxx-xxxx
    r"|PYSEC-\d{4}-\d{2,5}"                   # PYSEC-2024-123
    r"|GSD-\d{4}-\d{4,5}"                     # GSD-2024-12345
    r"|wid-sec-w-\d{4}-\d{4}"                 # CERT-Bund
    r"|cisco-sa-\d{8}-[a-zA-Z0-9]+"           # Cisco SA
    r"|RHSA-\d{4}:\d{4}"                      # Red Hat SA
    r"|msrc_CVE-\d{4}-\d{4,}"                 # MSRC
    r"|CERTFR-\d{4}-[A-Z]{3}-\d{3}"           # CERT-FR
    r"|RUSTSEC-\d{4}-\d{4}"                   # RustSec
    r"|SNYK-[A-Z]+-[A-Z0-9]+-\d+"             # Snyk
    r"|INTEL-SA-\d{5}"                        # Intel SA
    r")$",
    re.IGNORECASE,
)

_URL_RE = re.compile(
    r'^https?://'
    r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,}'
    r'(?::\d+)?(?:/[^\s]*)?$',
    re.IGNORECASE,
)

_VERSION_RE = re.compile(r'^\d+\.\d+$')


class RuleForm(FlaskForm):
    class Meta:
        # Allow JSON-based usage without CSRF (handled at API layer)
        csrf = False

    # ── Identity ──────────────────────────────────────────────────────────
    title = StringField('Title', validators=[
        DataRequired(message='A title is required.'),
        Length(min=3, max=512, message='Title must be between 3 and 512 characters.'),
    ])
    original_uuid = StringField('Original UUID', validators=[
        Optional(),
        Length(max=36, message='UUID must not exceed 36 characters.'),
    ])

    # ── Format & Classification ───────────────────────────────────────────
    format_id = StringField('Format', validators=[
        DataRequired(message='Please select a format.'),
    ])
    version = StringField('Version', validators=[
        Optional(),
        Length(max=32),
    ])
    status = StringField('Status', validators=[Optional()])

    severity   = StringField('Severity',   validators=[Optional()])
    confidence = StringField('Confidence', validators=[Optional()])

    # JSON-encoded lists submitted as strings
    platforms    = HiddenField('Platforms',     validators=[Optional()])   # JSON array string
    mitre_attack = HiddenField('MITRE ATT&CK', validators=[Optional()])   # JSON array string

    # ── Content ───────────────────────────────────────────────────────────
    content = TextAreaField('Rule content', validators=[
        DataRequired(message='Rule content is required.'),
        Length(min=10, message='Content seems too short (min 10 characters).'),
    ])
    description     = TextAreaField('Description',     validators=[Optional()])
    false_positives = TextAreaField('False positives', validators=[Optional()])

    # ── Authorship ────────────────────────────────────────────────────────
    author  = StringField('Author',  validators=[Optional(), Length(max=256)])
    license = StringField('License', validators=[Optional(), Length(max=128)])
    source  = StringField('Source',  validators=[Optional(), Length(max=256)])

    # References: one URL per line, submitted as a newline-separated string
    references_raw = TextAreaField('References', validators=[Optional()])

    # Dates — submitted as ISO strings (YYYY-MM-DD)
    creation_date = StringField('Creation date', validators=[Optional()])
    last_modif    = StringField('Last modified',  validators=[Optional()])

    # ── Visibility ────────────────────────────────────────────────────────
    is_public = BooleanField('Public', default=True)

    # ── Relations (comma-separated UUIDs / identifiers) ──────────────────
    tag_ids = HiddenField('Tag UUIDs',   validators=[Optional()])   # comma-sep tag UUIDs
    cve_ids = StringField('Vulnerability IDs', validators=[Optional()])

    submit = SubmitField('Create rule')

    # ── Custom validators ─────────────────────────────────────────────────

    def validate_status(self, field):
        v = (field.data or '').strip()
        if v and v not in STATUSES:
            raise ValidationError(f'Invalid status. Allowed: {", ".join(STATUSES)}.')

    def validate_severity(self, field):
        v = (field.data or '').strip()
        if v and v not in SEVERITIES:
            raise ValidationError(f'Invalid severity. Allowed: {", ".join(SEVERITIES)}.')

    def validate_confidence(self, field):
        v = (field.data or '').strip()
        if v and v not in CONFIDENCES:
            raise ValidationError(f'Invalid confidence. Allowed: {", ".join(CONFIDENCES)}.')

    def validate_title(self, field):
        from app.core.db_class.rule import Rule
        existing = Rule.query.filter_by(title=field.data, is_deleted=False).first()
        if existing:
            raise ValidationError(
                f'A rule named "{field.data}" already exists ({existing.uuid}).'
            )

    def validate_content(self, field):
        import hashlib
        from app.core.db_class.rule import Rule
        content = (field.data or '').strip()
        if not content:
            return
        h = hashlib.sha256(content.encode('utf-8')).hexdigest()
        existing = Rule.query.filter_by(rule_hash=h, is_deleted=False).first()
        if existing:
            raise ValidationError(
                f'This rule content already exists: "{existing.title}" ({existing.uuid}).'
            )

    def validate_version(self, field):
        v = (field.data or '').strip()
        if not v:
            return
        if not _VERSION_RE.match(v):
            raise ValidationError(
                'Version must be in X.Y format (e.g. 1.0, 2.3).'
            )

    def validate_format_id(self, field):
        from app.core.db_class.rule import FormatRule
        fmt = FormatRule.query.filter_by(uuid=field.data, is_active=True).first()
        if not fmt:
            raise ValidationError('Unknown or inactive format.')

    def validate_references_raw(self, field):
        if not field.data:
            return
        lines = [l.strip() for l in field.data.splitlines() if l.strip()]
        invalid = [l for l in lines if not _URL_RE.match(l)]
        if invalid:
            raise ValidationError(
                f'Invalid URL(s): {", ".join(invalid[:3])}'
                + (' …' if len(invalid) > 3 else '') + '. Each reference must be a full URL.'
            )

    def validate_cve_ids(self, field):
        if not field.data:
            return
        entries = [e.strip() for e in re.split(r'[\s,;]+', field.data.strip()) if e.strip()]
        if not entries:
            return
        invalid = [e for e in entries if not _CVE_PATTERN.match(e)]
        if invalid:
            raise ValidationError(
                f'Invalid vulnerability ID(s): {", ".join(invalid)}. '
                'Accepted: CVE, GCVE, GHSA, PYSEC, GSD, CERT-Bund, Cisco, RHSA, MSRC, CERT-FR, RUSTSEC, SNYK, INTEL-SA.'
            )
        # Normalize to uppercase, deduplicate
        field.data = ','.join(dict.fromkeys(e.upper() for e in entries))

    def validate_creation_date(self, field):
        v = (field.data or '').strip()
        if not v:
            return
        try:
            from datetime import datetime
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValidationError('Date must be in YYYY-MM-DD format.')

    def validate_mitre_attack(self, field):
        import json
        v = (field.data or '').strip()
        if not v:
            return
        try:
            items = json.loads(v)
        except (ValueError, TypeError):
            raise ValidationError('MITRE ATT&CK must be a valid JSON array.')
        mitre_re = re.compile(r'^T\d{4}(\.\d{3})?$')
        invalid = [i for i in items if not mitre_re.match(str(i))]
        if invalid:
            raise ValidationError(
                f'Invalid MITRE ATT&CK ID(s): {", ".join(invalid[:5])}. '
                'Expected format: T1059 or T1059.001.'
            )

    def parsed_references(self):
        """Return references as a list of URLs."""
        if not self.references_raw.data:
            return []
        return [l.strip() for l in self.references_raw.data.splitlines() if l.strip()]

    def parsed_platforms(self):
        import json
        v = (self.platforms.data or '').strip()
        if not v:
            return []
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return []

    def parsed_mitre(self):
        import json
        v = (self.mitre_attack.data or '').strip()
        if not v:
            return []
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return []

    def parsed_cve_ids(self):
        v = (self.cve_ids.data or '').strip()
        if not v:
            return []
        return [e.strip() for e in v.split(',') if e.strip()]

    def parsed_tag_ids(self):
        v = (self.tag_ids.data or '').strip()
        if not v:
            return []
        return [e.strip() for e in v.split(',') if e.strip()]
