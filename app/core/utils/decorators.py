"""
decorators.py — Route access control.

HTML routes  → use require_permission(key) only. Never mix with @login_required.
API routes   → use method_decorators = [api_required] or [admin_required].

require_permission(key) behaviour:
  key = None          → any authenticated user
  key = 'admin_only'  → role.admin = True required
  key = 'some.perm'   → user must have that permission key (admins always pass)
"""

from functools import wraps
from flask import abort, request, redirect, url_for
from flask_login import current_user
from .utils import get_user_api, verif_api_key


# ── HTML routes ───────────────────────────────────────────────────────────────

def require_permission(key=None, public=False):
    """Universal decorator for HTML routes.

    Replaces @login_required, @admin_required, and the old @feature_required.
    Always redirects to login when unauthenticated (never 403 on public forms),
    unless public=True in which case anonymous users are served without redirect.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Public pages — no auth or permission check at all
            if public:
                return f(*args, **kwargs)

            if not current_user.is_authenticated:
                return redirect(url_for('account.login', next=request.url))

            if key is None:
                return f(*args, **kwargs)

            if key == 'admin_only':
                if not current_user.is_admin():
                    abort(403)
                return f(*args, **kwargs)

            if not current_user.has_permission(key):
                abort(403)

            return f(*args, **kwargs)
        return decorated
    return decorator


# ── API routes ────────────────────────────────────────────────────────────────
# api_require_permission(key) is the single decorator for ALL API endpoints.
# It handles both X-API-KEY (external) and session auth (internal frontend).
# Same permission keys as require_permission() and hasPerm() on the frontend.

def api_require_permission(key=None):
    """Universal API decorator — mirrors require_permission() for the API layer.

    key=None         → any authenticated user (session or valid API key)
    key='admin_only' → admin flag required
    key='some.perm'  → user must have that permission key (admins always pass)

    Auth priority:
      1. X-API-KEY present  → validate key, then check permission
      2. No X-API-KEY        → validate session, then check permission
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            api_key = request.headers.get('X-API-KEY')

            if api_key:
                user = get_user_api(api_key)
                if not user:
                    abort(403)
                _check_permission(user, key)
            else:
                if not current_user.is_authenticated:
                    abort(403)
                _check_permission(current_user, key)

            return f(*args, **kwargs)
        return decorated
    return decorator


def _check_permission(user, key):
    if key is None:
        return
    if key == 'admin_only':
        if not user.is_admin():
            abort(403)
    elif not user.has_permission(key):
        abort(403)


# ── Legacy aliases — kept so existing API files compile without changes ────────
# These will be removed once all method_decorators are migrated.

def admin_required(f):
    return api_require_permission('admin_only')(f)

def api_required(f):
    return api_require_permission()(f)


