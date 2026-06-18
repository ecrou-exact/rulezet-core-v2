"""rules_api.py — Rules API endpoints."""
import json
from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..core.db_class.rule import FormatRule
from ..features.rules.form import RuleForm
from ..features.rules.rules_core import create_rule_core
from ..features.rulecast.rulecast_core import validate_rule_with_cast

rules_ns = Namespace('rules', description='Detection rules')


@rules_ns.route('/formats')
class RuleFormats(Resource):

    @api_require_permission(None)
    def get(self):
        """List all active rule formats."""
        fmts = FormatRule.query.filter_by(is_active=True).order_by(FormatRule.name).all()
        return {'formats': [f.to_json_light() for f in fmts]}, 200


@rules_ns.route('/')
class RuleList(Resource):

    @api_require_permission('rules.create')
    def post(self):
        """Create a new rule."""
        body = request.get_json(silent=True) or {}

        # Normalize body for RuleForm:
        # - frontend sends format_uuid; form field is format_id
        # - SelectField rejects None — coerce to '' so Optional() kicks in
        form_data = dict(body)
        form_data['format_id']  = form_data.pop('format_uuid', '') or ''
        form_data['severity']   = form_data.get('severity')   or ''
        form_data['confidence'] = form_data.get('confidence') or ''
        form_data['status']     = form_data.get('status')     or 'stable'

        form = RuleForm(data=form_data)

        if not form.validate():
            return {'errors': form.errors}, 200

        # ── RuleCast validation ───────────────────────────────────────────────
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
