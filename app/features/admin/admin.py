from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

from ...core.utils.decorators import require_permission
from ...core.db_class.site_config import get_site_bool
from ...core.utils.permissions import get_by_group
from ...features.account.account_core import get_all_roles
from .admin_core import get_user_or_404, get_role_or_404

admin_blueprint = Blueprint('admin', __name__)


@admin_blueprint.route('/', strict_slashes=False)
@require_permission(None)
def index():
    """Redirect to the first admin section the user can access."""
    if current_user.is_admin() or current_user.has_permission('users.view'):
        return redirect(url_for('admin.users'))
    if current_user.has_permission('admin.roles'):
        return redirect(url_for('admin.roles'))
    if current_user.has_permission('logs.view'):
        return redirect(url_for('admin.logs'))
    if current_user.has_permission('jobs.manage'):
        return redirect('/jobs/')
    if current_user.has_permission('tags.view'):
        return redirect('/tags/')
    return redirect('/')


@admin_blueprint.route('/users')
@require_permission('users.view')
def users():
    return render_template(
        'admin/users.html',
        allow_registration=get_site_bool('allow_registration', default=True),
        allow_login=get_site_bool('allow_login', default=True),
        email_verification_enabled=get_site_bool('email_verification_enabled', default=False),
        weather_widget_enabled=get_site_bool('weather_widget_enabled', default=False),
    )


@admin_blueprint.route('/users/<int:uid>')
@require_permission('users.view')
def user_detail(uid):
    user  = get_user_or_404(uid)
    roles = get_all_roles()
    return render_template('admin/user_detail.html', user=user, roles=roles)


@admin_blueprint.route('/logs')
@require_permission('logs.view')
def logs():
    return render_template('admin/logs.html')


@admin_blueprint.route('/roles')
@require_permission('admin.roles')
def roles():
    return render_template('admin/roles.html')


@admin_blueprint.route('/roles/new')
@admin_blueprint.route('/roles/<int:role_id>')
@require_permission('admin.roles')
def role_detail(role_id=None):
    role = get_role_or_404(role_id) if role_id else None
    return render_template(
        'admin/role_detail.html',
        role=role,
        permissions_by_group=get_by_group(),
    )
