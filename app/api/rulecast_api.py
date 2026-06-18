"""rulecast_api.py — RuleCast admin API endpoints."""
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..features.rulecast.rulecast_core import import_formats_from_cast

rulecast_ns = Namespace('rulecast', description='RuleCast management')


@rulecast_ns.route('/import-formats')
class RulecastImportFormats(Resource):

    @api_require_permission('admin_only')
    def post(self):
        """Upsert all RuleCast formats into the FormatRule table."""
        result = import_formats_from_cast(current_user.id)
        status = 200 if not result['errors'] else 207
        return result, status
