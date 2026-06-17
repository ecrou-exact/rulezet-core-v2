"""dynamic_pages.py — Generic route handler for Template Studio pages."""
from flask import Blueprint, render_template, abort
from flask_login import current_user
from ...core.db_class.page_definition import PageDefinition
from ...core.utils.decorators import require_permission

dynamic_pages_blueprint = Blueprint('dynamic_pages', __name__)


@dynamic_pages_blueprint.route('/<string:slug>')
@require_permission(None)
def view_page(slug):
    page = PageDefinition.query.filter_by(slug=slug, is_active=True, is_published=True).first()
    if not page:
        abort(404)

    perm = page.required_permission
    if perm == 'admin_only' and not current_user.is_admin():
        abort(403)
    elif perm and perm != 'admin_only' and not current_user.has_permission(perm):
        abort(403)

    return render_template('dynamic_pages/page.html', page=page, preview_mode=False)
