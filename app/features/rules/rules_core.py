"""rules_core.py — Business logic for the rules feature."""
from datetime import datetime

from ... import db
from ...core.db_class.rule import Rule, FormatRule, RuleTag, RuleCVE, RuleHistory
from ...core.db_class.tag import Tag
from ...core.utils.logger import log_action


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_formats():
    """Return all active FormatRule objects, ordered by name."""
    return FormatRule.query.filter_by(is_active=True).order_by(FormatRule.name).all()


# ── Create ────────────────────────────────────────────────────────────────────

def create_rule_core(data: dict, user_id: int):
    """
    Create a new Rule from validated form data.

    data keys (all optional unless stated):
      format_uuid, title*, content*, description, version,
      status, severity, confidence, platforms (list), mitre_attack (list),
      references (list of URLs), false_positives,
      author, license, source,
      creation_date (str YYYY-MM-DD), last_modif (str),
      is_public, original_uuid,
      tag_uuids (list), cve_ids (list of strings)

    Returns (rule, msg) on success, (None, msg) on error.
    """
    try:
        # Resolve format
        fmt = FormatRule.query.filter_by(uuid=data.get('format_uuid'), is_active=True).first()
        if not fmt:
            return None, 'Unknown or inactive format.'

        # Parse dates
        creation_date = None
        if data.get('creation_date'):
            try:
                creation_date = datetime.strptime(data['creation_date'], '%Y-%m-%d')
            except ValueError:
                pass

        last_modif = None
        if data.get('last_modif'):
            try:
                last_modif = datetime.strptime(data['last_modif'], '%Y-%m-%d')
            except ValueError:
                pass

        def _s(val, default=''):
            return (val or default).strip()

        rule = Rule(
            title           = _s(data.get('title')),
            content         = _s(data.get('content')),
            description     = _s(data.get('description')) or None,
            format_id       = fmt.id,
            version         = _s(data.get('version')) or '1.0',
            status          = _s(data.get('status')) or 'stable',
            severity        = _s(data.get('severity')) or None,
            confidence      = _s(data.get('confidence')) or None,
            platforms       = data.get('platforms')    or [],
            mitre_attack    = data.get('mitre_attack') or [],
            references      = data.get('references')   or [],
            false_positives = _s(data.get('false_positives')) or None,
            author          = _s(data.get('author'))   or None,
            license         = _s(data.get('license'))  or None,
            source          = _s(data.get('source'))   or None,
            is_public       = bool(data.get('is_public', True)),
            original_uuid   = _s(data.get('original_uuid')) or None,
            creation_date   = creation_date,
            last_modif      = last_modif,
            user_id         = user_id,
        )
        rule.compute_hash()
        db.session.add(rule)
        db.session.flush()   # get rule.id before linking

        # ── Tags ──────────────────────────────────────────────────────────
        for tag_uuid in (data.get('tag_uuids') or []):
            tag = Tag.query.filter_by(uuid=tag_uuid, is_active=True).first()
            if tag:
                db.session.add(RuleTag(rule_id=rule.id, tag_id=tag.id, created_by=user_id))

        # ── CVEs ──────────────────────────────────────────────────────────
        for cve_id in (data.get('cve_ids') or []):
            cve_id = cve_id.strip().upper()
            if cve_id:
                db.session.add(RuleCVE(rule_id=rule.id, cve_id=cve_id))

        # ── History snapshot ───────────────────────────────────────────────
        entry = RuleHistory.record(rule, change_type='import', changed_by=user_id)
        db.session.add(entry)

        db.session.commit()

        log_action(
            title=f'Rule created: {rule.title}',
            action='create',
            category='rules',
            level='success',
            object_type='rule',
            object_id=rule.id,
            is_public=rule.is_public,
            meta={'format': fmt.name, 'uuid': rule.uuid},
        )
        return rule, 'Rule created successfully.'

    except Exception as exc:
        db.session.rollback()
        return None, f'Error creating rule: {exc}'
