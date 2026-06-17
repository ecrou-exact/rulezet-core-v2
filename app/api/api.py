import os
from flask import Blueprint, g, request
from flask_restx import Api

api_blueprint = Blueprint(
    "api", __name__, url_prefix="/api"
)

authorizations = {
    "apikey": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-KEY",
    }
}

def version():
    with open(os.path.join(os.getcwd(),"version")) as read_version:
        loc = read_version.readlines()
    return loc[0].rstrip()


api = Api(api_blueprint,
    title='flask-launchpad API',
    description="<a href='https://github.com/ecrou-exact/flask-launchpad' rel='noreferrer' target='_blank'>"
    "<img src='/static/image/logo.png'  /></a><br />"
    'API to query flask-launchpad.',
    version=version(),
    doc='/',
    security="apikey",
    authorizations=authorizations
)

from .account_api import account_ns
from .config_api import config_ns
from .admin_api import admin_ns
from .log_api import log_ns
from .role_api import role_ns
from .site_settings_api import site_settings_ns
from .comment_api import comment_ns
from .jobs_api import jobs_ns
from .database_api import database_ns
from .tags_api import tags_ns
from .connectors_api import connectors_ns

api.add_namespace(account_ns, path="/account")
api.add_namespace(config_ns, path="/config")
api.add_namespace(admin_ns, path="/admin")
api.add_namespace(log_ns, path="/log")
api.add_namespace(role_ns, path="/roles")
api.add_namespace(site_settings_ns, path="/site-settings")
api.add_namespace(comment_ns, path="/comments")
api.add_namespace(jobs_ns, path="/jobs")
api.add_namespace(database_ns, path="/database")
api.add_namespace(tags_ns, path="/tags")
api.add_namespace(connectors_ns, path="/connectors")


# ── Automatic API call logging ────────────────────────────────────────────────

_SENSITIVE_KEYS = {'password', 'password_hash', 'api_key', 'token', 'secret'}

def _sanitize(obj):
    if not isinstance(obj, dict):
        return obj
    return {k: '***' if k in _SENSITIVE_KEYS else v for k, v in obj.items()}


@api_blueprint.before_request
def _store_request_body():
    g._api_req_body = request.get_json(silent=True)


@api_blueprint.after_request
def _log_api_call(response):
    try:
        # Only log external API calls (identified by X-API-KEY header)
        # Internal frontend calls use session auth and must not be logged here
        if not request.headers.get('X-API-KEY'):
            return response

        # Skip Swagger UI assets
        if request.path in ('/', '') or '/swaggerui/' in request.path:
            return response

        status = response.status_code
        if status < 300:
            level = 'success'
        elif status < 500:
            level = 'warning'
        else:
            level = 'error'

        resp_body = response.get_json(silent=True)
        req_body  = _sanitize(getattr(g, '_api_req_body', None))

        from ..core.utils.logger import log_action
        log_action(
            f"{request.method} {request.path} → {status}",
            "api_call",
            category="api",
            level=level,
            is_public=False,
            meta={
                "method":       request.method,
                "path":         request.path,
                "status_code":  status,
                "request_body": req_body,
                "response":     resp_body,
            },
        )
    except Exception:
        pass
    return response
