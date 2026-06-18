"""misp_export.py — Convert Rule objects to MISP event/object and STIX.

Logic ported from rulezet-core/app/features/misp/rule/misp_object.py.
Adapted for the v2 Rule model:
  - rule.content  (was rule.to_string)
  - rule.cve_records relationship (was rule.cve_id JSON string)
  - rule.rule_tags_assocs relationship (was RuleModel.get_tags_for_rule)
"""
import json
import requests
from ...core.db_class.rule import Rule

try:
    from pymisp import MISPEvent, MISPObject
    _PYMISP = True
except ImportError:
    _PYMISP = False


class MispNotAvailableError(RuntimeError):
    pass


def _require_pymisp():
    if not _PYMISP:
        raise MispNotAvailableError(
            'pymisp is not installed. Run: pip install pymisp'
        )


# ── Format-specific content object builders ───────────────────────────────────

def _make_yara_object(rule: Rule):
    obj = MISPObject(name='yara', ignore_warning=True)
    obj['meta-category'] = 'misc'
    if rule.content:
        obj.add_attribute('yara', value=rule.content)
    if rule.title:
        obj.add_attribute('yara-rule-name', value=rule.title)
    return obj


def _make_sigma_object(rule: Rule):
    obj = MISPObject(name='sigma', ignore_warning=True)
    obj['meta-category'] = 'misc'
    if rule.content:
        obj.add_attribute('sigma', value=rule.content, type='sigma', to_ids=True)
    if rule.title:
        obj.add_attribute('sigma-rule-name', value=rule.title, type='text')
    return obj


def _make_suricata_object(rule: Rule):
    obj = MISPObject(name='suricata', ignore_warning=True)
    obj['meta-category'] = 'network'
    if rule.content:
        obj.add_attribute('suricata', value=rule.content, type='snort', to_ids=True)
    if rule.source:
        obj.add_attribute('ref', value=rule.source, type='link')
    return obj


def _make_nse_object(rule: Rule):
    obj = MISPObject(name='nse', ignore_warning=True)
    obj['meta-category'] = 'network'
    obj.uuid = rule.uuid
    if rule.content:
        obj.add_attribute('nse', value=rule.content, type='text')
    if rule.title:
        obj.add_attribute('nse-script-name', value=rule.title, type='text')
    return obj


def _make_wazuh_object(rule: Rule):
    obj = MISPObject(name='wazuh-rule', ignore_warning=True)
    obj['meta-category'] = 'misc'
    if rule.content:
        obj.add_attribute('wazuh-rule', value=rule.content, type='text')
    if rule.title:
        obj.add_attribute('rule-id', value=rule.title, type='text')
    return obj


def _make_crs_object(rule: Rule):
    obj = MISPObject(name='owasp-crs-rule', ignore_warning=True)
    obj['meta-category'] = 'network'
    if rule.title:
        obj.add_attribute('rule-id', value=rule.title, type='text')
    if rule.content:
        obj.add_attribute('raw-rule', value=rule.content, type='text')
    return obj


def _make_nova_object(rule: Rule):
    obj = MISPObject(name='nova-rule', ignore_warning=True)
    obj['meta-category'] = 'detection'
    if rule.content:
        obj.add_attribute('raw-rule', value=rule.content, type='text')
    if rule.title:
        obj.add_attribute('rule-name', value=rule.title, type='text')
    return obj


_FORMAT_MAKERS = {
    'yara':     _make_yara_object,
    'sigma':    _make_sigma_object,
    'suricata': _make_suricata_object,
    'nse':      _make_nse_object,
    'wazuh':    _make_wazuh_object,
    'crs':      _make_crs_object,
    'nova':     _make_nova_object,
}


# ── Public API ────────────────────────────────────────────────────────────────

def rule_to_content_misp_object(rule: Rule):
    """Return the format-specific MISP content MISPObject for a rule."""
    _require_pymisp()
    fmt = (rule.format or '').lower()
    maker = _FORMAT_MAKERS.get(fmt)
    if maker:
        return maker(rule)
    obj = MISPObject(name=fmt or 'generic-rule', ignore_warning=True)
    if rule.content:
        obj.add_attribute(fmt or 'content', value=rule.content, type='text')
    return obj


def rule_to_metadata_misp_object(rule: Rule):
    """Return the rulezet-metadata MISPObject for a rule."""
    _require_pymisp()
    obj = MISPObject(name='rulezet-metadata', ignore_warning=True)
    obj.add_attribute('title', value=rule.title)
    obj.add_attribute('uuid', value=rule.uuid)
    if rule.version:
        obj.add_attribute('version', value=rule.version)
    if rule.format:
        obj.add_attribute('format', value=rule.format)
    if rule.license:
        obj.add_attribute('license', value=rule.license)
    if rule.description:
        obj.add_attribute('description', value=rule.description)
    if rule.source:
        obj.add_attribute('source', value=rule.source)
    if rule.author:
        obj.add_attribute('author', value=rule.author)
    if rule.original_uuid:
        obj.add_attribute('original-uuid', value=rule.original_uuid)
    if rule.user_id:
        obj.add_attribute('user-id', value=str(rule.user_id))
    if rule.creation_date:
        obj.add_attribute('creation-date', value=rule.creation_date)
    if rule.last_modif:
        obj.add_attribute('last-modif', value=rule.last_modif)
    if rule.vote_up is not None:
        obj.add_attribute('vote-up', value=rule.vote_up)
    if rule.vote_down is not None:
        obj.add_attribute('vote-down', value=rule.vote_down)
    if rule.github_path:
        obj.add_attribute('github-path', value=rule.github_path)
    for cve_rec in rule.cve_records:
        if cve_rec.cve_id:
            obj.add_attribute('cve-id', value=cve_rec.cve_id)
    return obj


def get_misp_object_json(rule: Rule) -> dict:
    """Return MISP Object list JSON (no event wrapper) for a rule."""
    _require_pymisp()
    event = MISPEvent()
    meta_obj    = event.add_object(rule_to_metadata_misp_object(rule))
    content_obj = event.add_object(rule_to_content_misp_object(rule))
    meta_obj.add_reference(content_obj.uuid, 'related-to')
    raw = json.loads(event.to_json())
    return {'Object': raw.get('Object', [])}


def get_misp_event_json(rule: Rule) -> dict:
    """Return a full MISP Event JSON for a rule."""
    _require_pymisp()
    event = MISPEvent()
    event.info = f'Rule — {rule.title}'
    meta_obj    = event.add_object(rule_to_metadata_misp_object(rule))
    content_obj = event.add_object(rule_to_content_misp_object(rule))
    meta_obj.add_reference(content_obj.uuid, 'related-to')
    for cve_rec in rule.cve_records:
        if cve_rec.cve_id:
            attr = event.add_attribute('vulnerability', cve_rec.cve_id)
            content_obj.add_reference(attr.uuid, 'related-to')
    for assoc in rule.rule_tags_assocs:
        if assoc.tag and assoc.tag.is_active:
            ext_id = getattr(assoc.tag, 'external_id', None)
            if ext_id:
                event.add_tag(**{'name': assoc.tag.name, 'uuid': ext_id})
            else:
                event.add_tag(assoc.tag.name)
    return json.loads(event.to_json())


def get_stix_json(rule: Rule) -> dict | None:
    """Convert the rule's MISP event to STIX via the cti-transmute.org API."""
    misp_event = get_misp_event_json(rule)
    try:
        resp = requests.post(
            'https://cti-transmute.org/api/convert/misp_to_stix',
            json=misp_event,
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None
