"""rules_api.py — Rules API endpoints."""
import json
from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..core.db_class.rule import FormatRule
from ..features.rules.form import RuleForm
from ..features.rules.rules_core import create_rule_core

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

        # Populate a RuleForm from the JSON body for validation
        form = RuleForm(data=body)

        if not form.validate():
            return {'errors': form.errors}, 422

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
