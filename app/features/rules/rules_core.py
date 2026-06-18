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


def get_rule_by_uuid(uuid: str) -> Rule | None:
    """Return an active (not deleted) Rule by UUID, or None."""
    return Rule.query.filter_by(uuid=uuid, is_deleted=False).first()


def get_rules_paginated(page=1, per_page=20, search='', sort='created_at', direction='desc',
                        format_uuid='', severity='', status='') -> dict:
    """Return a page of rules with optional filters. Used by the API list endpoint."""
    q = Rule.query.filter_by(is_deleted=False)

    if format_uuid:
        fmt = FormatRule.query.filter_by(uuid=format_uuid, is_active=True).first()
        if fmt:
            q = q.filter(Rule.format_id == fmt.id)
        else:
            q = q.filter(db.false())

    if severity:
        q = q.filter(Rule.severity == severity)
    if status:
        q = q.filter(Rule.status == status)

    if search:
        like = f'%{search}%'
        q = q.filter(
            db.or_(Rule.title.ilike(like), Rule.description.ilike(like))
        )

    _SORT = {
        'title':      Rule.title,
        'created_at': Rule.created_at,
        'severity':   Rule.severity,
        'status':     Rule.status,
    }
    col = _SORT.get(sort, Rule.created_at)
    q = q.order_by(col.desc() if direction == 'desc' else col.asc())

    total       = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    rules       = q.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for rule in rules:
        d = rule.to_json()
        d['format_color'] = rule.format_rule.color if rule.format_rule else None
        d['format_icon']  = rule.format_rule.icon  if rule.format_rule else None
        d['tags'] = [a.to_json() for a in rule.rule_tags_assocs.limit(5)]
        items.append(d)

    return {
        'items':       items,
        'total':       total,
        'total_pages': total_pages,
        'page':        page,
        'per_page':    per_page,
    }


def soft_delete_rule(rule: Rule, user_id: int) -> str:
    """Soft-delete a rule and log the action."""
    rule.is_deleted    = True
    rule.deleted_at    = datetime.utcnow()
    rule.deleted_by_id = user_id
    db.session.commit()
    log_action(
        title=f'Rule deleted: {rule.title}',
        action='delete',
        category='rules',
        level='warning',
        object_type='rule',
        object_id=rule.id,
        is_public=False,
        meta={'uuid': rule.uuid},
    )
    return 'Rule deleted.'


def bulk_delete_rules(uuids: list, user_id: int) -> int:
    """Soft-delete multiple rules by UUID list. Returns count deleted."""
    count = 0
    now   = datetime.utcnow()
    for uuid in uuids:
        rule = Rule.query.filter_by(uuid=uuid, is_deleted=False).first()
        if rule:
            rule.is_deleted    = True
            rule.deleted_at    = now
            rule.deleted_by_id = user_id
            count += 1
    if count:
        db.session.commit()
        log_action(
            title=f'Bulk delete: {count} rule(s)',
            action='bulk_delete',
            category='rules',
            level='warning',
            object_type='rule',
            object_id=None,
            is_public=False,
            meta={'count': count},
        )
    return count


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
