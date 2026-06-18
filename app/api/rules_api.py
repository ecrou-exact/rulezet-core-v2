"""rules_api.py — Rules API endpoints."""
import json
from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..core.db_class.rule import FormatRule
from ..features.rules.form import RuleForm
from ..features.rules.rules_core import (
    create_rule_core, get_formats, get_rule_by_uuid,
    get_rules_paginated, soft_delete_rule, bulk_delete_rules,
)
from ..features.rules.misp_export import (
    MispNotAvailableError,
    get_misp_object_json, get_misp_event_json, get_stix_json,
)
from ..features.rulecast.rulecast_core import validate_rule_with_cast

rules_ns = Namespace('rules', description='Detection rules')


@rules_ns.route('/formats')
class RuleFormats(Resource):

    @api_require_permission(None, public=True)
    def get(self):
        """List all active rule formats."""
        fmts = FormatRule.query.filter_by(is_active=True).order_by(FormatRule.name).all()
        return {'formats': [f.to_json_light() for f in fmts]}, 200


@rules_ns.route('/')
class RuleList(Resource):

    @api_require_permission('rules.view', public=True)
    def get(self):
        """List rules with pagination and optional filters."""
        page        = request.args.get('page',         1,    type=int)
        per_page    = min(request.args.get('per_page', 20,   type=int), 100)
        search      = request.args.get('search',       '',   type=str).strip()
        sort        = request.args.get('sort',         'created_at', type=str)
        direction   = request.args.get('dir',          'desc', type=str)
        format_uuid = request.args.get('format_uuid',  '',   type=str).strip()
        severity    = request.args.get('severity',     '',   type=str).strip()
        status      = request.args.get('status',       '',   type=str).strip()

        return get_rules_paginated(
            page=page, per_page=per_page, search=search,
            sort=sort, direction=direction,
            format_uuid=format_uuid, severity=severity, status=status,
        ), 200

    @api_require_permission('rules.create')
    def post(self):
        """Create a new rule."""
        body = request.get_json(silent=True) or {}

        form_data = dict(body)
        form_data['format_id']  = form_data.pop('format_uuid', '') or ''
        form_data['severity']   = form_data.get('severity')   or ''
        form_data['confidence'] = form_data.get('confidence') or ''
        form_data['status']     = form_data.get('status')     or 'stable'

        form = RuleForm(data=form_data)

        if not form.validate():
            return {'errors': form.errors}, 200

        format_uuid = body.get('format_uuid')
        fmt_obj     = FormatRule.query.filter_by(uuid=format_uuid, is_active=True).first()
        if fmt_obj and form.content.data:
            cast = validate_rule_with_cast(fmt_obj.name, form.content.data)
            if cast is not None and not cast.get('ok'):
                invalid = cast.get('invalid', 0)
                total   = cast.get('total', 0)
                errors_per_rule = []
                for r in cast.get('rules', []):
                    if not r.get('ok') and r.get('errors'):
                        errors_per_rule.extend(r['errors'])
                summary = f"RuleCast: {invalid}/{total} rule(s) failed validation"
                if errors_per_rule:
                    summary += ' — ' + ' | '.join(errors_per_rule[:3])
                return {
                    'errors':  {'content': summary},
                    'rulecast': cast,
                }, 200

        rule, msg = create_rule_core(
            data={
                'format_uuid':    body.get('format_uuid'),
                'title':          form.title.data,
                'content':        form.content.data,
                'description':    form.description.data,
                'version':        form.version.data or '1.0',
                'status':         form.status.data,
                'severity':       form.severity.data or None,
                'confidence':     form.confidence.data or None,
                'platforms':      form.parsed_platforms(),
                'mitre_attack':   form.parsed_mitre(),
                'references':     form.parsed_references(),
                'false_positives': form.false_positives.data,
                'author':         form.author.data,
                'license':        form.license.data,
                'source':         form.source.data,
                'creation_date':  form.creation_date.data,
                'last_modif':     form.last_modif.data,
                'is_public':      form.is_public.data,
                'original_uuid':  form.original_uuid.data,
                'tag_uuids':      form.parsed_tag_ids(),
                'cve_ids':        form.parsed_cve_ids(),
            },
            user_id=current_user.id,
        )

        if rule is None:
            return {'message': msg}, 400

        return {'message': msg, 'uuid': rule.uuid}, 201


@rules_ns.route('/<string:uuid>')
class RuleDetail(Resource):

    @api_require_permission('rules.view', public=True)
    def get(self, uuid):
        """Get full rule detail."""
        rule = get_rule_by_uuid(uuid)
        if not rule:
            return {'message': 'Rule not found.'}, 404
        d = rule.to_json_detail()
        # Include format color/icon for UI
        if rule.format_rule:
            d['identity']['format_color'] = rule.format_rule.color
            d['identity']['format_icon']  = rule.format_rule.icon
        # Include tags and CVEs flat for convenience
        d['tags'] = [a.to_json() for a in rule.rule_tags_assocs]
        d['cves'] = [c.to_json() for c in rule.cve_records]
        return d, 200

    @api_require_permission('rules.delete')
    def delete(self, uuid):
        """Soft-delete a rule."""
        rule = get_rule_by_uuid(uuid)
        if not rule:
            return {'message': 'Rule not found.'}, 404
        msg = soft_delete_rule(rule, current_user.id)
        return {'message': msg}, 200


@rules_ns.route('/bulk')
class RuleBulk(Resource):

    @api_require_permission('rules.delete')
    def post(self):
        """Bulk actions on rules. action: 'delete' | 'export'."""
        body   = request.get_json(silent=True) or {}
        action = body.get('action', '')
        uuids  = body.get('uuids', [])

        if not uuids:
            return {'message': 'No rules selected.'}, 400

        if action == 'delete':
            count = bulk_delete_rules(uuids, current_user.id)
            return {'message': f'{count} rule(s) deleted.', 'count': count}, 200

        if action == 'export':
            from ..core.db_class.rule import Rule as RuleModel
            items = []
            for u in uuids:
                r = RuleModel.query.filter_by(uuid=u, is_deleted=False).first()
                if r:
                    items.append(r.to_json())
            return {'rules': items, 'count': len(items)}, 200

        return {'message': f'Unknown action: {action}'}, 400


@rules_ns.route('/<string:uuid>/export/<string:fmt>')
class RuleExport(Resource):

    @api_require_permission(None)
    def get(self, uuid, fmt):
        """Export a rule in the requested format: json | misp-object | misp-event | stix."""
        rule = get_rule_by_uuid(uuid)
        if not rule:
            return {'message': 'Rule not found.'}, 404

        if fmt == 'json':
            d = rule.to_json()
            d['format_color'] = rule.format_rule.color if rule.format_rule else None
            d['format_icon']  = rule.format_rule.icon  if rule.format_rule else None
            d['tags'] = [a.to_json() for a in rule.rule_tags_assocs]
            d['cves'] = [c.to_json() for c in rule.cve_records]
            return {'data': json.dumps(d, indent=2, default=str), 'format': 'json'}, 200

        try:
            if fmt == 'misp-object':
                data = get_misp_object_json(rule)
                return {'data': json.dumps(data, indent=2, default=str), 'format': 'misp-object'}, 200

            if fmt == 'misp-event':
                data = get_misp_event_json(rule)
                return {'data': json.dumps(data, indent=2, default=str), 'format': 'misp-event'}, 200

            if fmt == 'stix':
                data = get_stix_json(rule)
                if data is None:
                    return {'message': 'STIX conversion failed. The cti-transmute.org API may be unavailable.'}, 503
                return {'data': json.dumps(data, indent=2, default=str), 'format': 'stix'}, 200

        except MispNotAvailableError as e:
            return {'message': str(e)}, 503

        return {'message': f'Unknown export format: {fmt}'}, 400
