from flask import request
from flask_restx import Namespace, Resource

from ..core.utils.decorators import api_require_permission
from ..core.db_class.site_config import SiteConfig, get_site_bool, set_site_value
from ..core.utils.logger import log_action, api_category
from flask_login import current_user

admin_ns = Namespace('admin', description='Admin-only site configuration')

_ALLOWED_KEYS = {'allow_registration', 'allow_login', 'email_verification_enabled', 'weather_widget_enabled'}


@admin_ns.route('/site-config')
class SiteConfigList(Resource):
    method_decorators = [api_require_permission("admin.site_config")]

    def get(self):
        rows = SiteConfig.query.all()
        return {r.key: {'value': r.value, 'label': r.label} for r in rows}, 200

    def post(self):
        data = request.get_json(silent=True) or {}
        key   = data.get('key', '').strip()
        value = data.get('value')

        if key not in _ALLOWED_KEYS:
            return {'message': f'Unknown key. Allowed: {sorted(_ALLOWED_KEYS)}'}, 400
        if value is None:
            return {'message': 'value is required'}, 400

        uid = current_user.id if current_user.is_authenticated else None
        set_site_value(key, '1' if value else '0', user_id=uid)
        log_action(
            f"Site config updated: {key}",
            "site_config_update",
            category=api_category('admin'),
            level="info",
            object_type="site_config",
            object_id=key,
            is_public=False,
            meta={"key": key, "value": str(value)},
        )
        return {'key': key, 'value': str(value), 'message': 'Updated'}, 200
