"""template_studio.py — Admin routes for the Template Studio."""
from flask import Blueprint, render_template, request, abort, jsonify
from ...core.utils.decorators import require_permission
from ...core.utils.permissions import PERMISSIONS
from .template_studio_core import (
    list_pages_core,
    get_page_or_none,
    create_page_core,
    update_page_core,
    publish_page_core,
    unpublish_page_core,
    delete_page_core,
    hard_delete_page_core,
)

template_studio_blueprint = Blueprint('template_studio', __name__)

NAV_GROUPS = ['Navigation', 'Admin', 'Community']


def _perm_keys():
    return [{'key': k, 'label': v['label']} for k, v in PERMISSIONS.items()]


@template_studio_blueprint.route('/')
@require_permission('admin_only')
def index():
    pages = list_pages_core()
    return render_template('template_studio/index.html', pages=pages)


@template_studio_blueprint.route('/new')
@require_permission('admin_only')
def new_page():
    return render_template(
        'template_studio/builder.html',
        page=None,
        perm_keys=_perm_keys(),
        nav_groups=NAV_GROUPS,
    )


@template_studio_blueprint.route('/<string:uuid>')
@require_permission('admin_only')
def edit_page(uuid):
    page = get_page_or_none(uuid)
    if not page:
        abort(404)
    return render_template(
        'template_studio/builder.html',
        page=page,
        perm_keys=_perm_keys(),
        nav_groups=NAV_GROUPS,
    )


@template_studio_blueprint.route('/<string:uuid>/preview')
@require_permission('admin_only')
def preview_page(uuid):
    page = get_page_or_none(uuid)
    if not page:
        abort(404)
    return render_template('dynamic_pages/page.html', page=page, preview_mode=True)


# ── JSON action routes ────────────────────────────────────────────────────────

@template_studio_blueprint.route('/save', methods=['POST'])
@require_permission('admin_only')
def save_page():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'message': 'No data received'}), 400

    uuid_val = data.get('uuid')
    if uuid_val:
        page, msg = update_page_core(uuid_val, data)
    else:
        page, msg = create_page_core(data)

    if not page:
        return jsonify({'ok': False, 'message': msg}), 400

    return jsonify({'ok': True, 'message': msg, 'uuid': page.uuid}), 200


@template_studio_blueprint.route('/<string:uuid>/publish', methods=['POST'])
@require_permission('admin_only')
def publish_page(uuid):
    ok, msg = publish_page_core(uuid)
    if not ok:
        return jsonify({'ok': False, 'message': msg}), (404 if 'not found' in msg else 400)
    return jsonify({'ok': True, 'message': msg}), 200


@template_studio_blueprint.route('/<string:uuid>/unpublish', methods=['POST'])
@require_permission('admin_only')
def unpublish_page(uuid):
    ok, msg = unpublish_page_core(uuid)
    if not ok:
        return jsonify({'ok': False, 'message': msg}), (404 if 'not found' in msg else 400)
    return jsonify({'ok': True, 'message': msg}), 200


@template_studio_blueprint.route('/<string:uuid>/delete', methods=['POST'])
@require_permission('admin_only')
def delete_page(uuid):
    ok, msg = delete_page_core(uuid)
    if not ok:
        return jsonify({'ok': False, 'message': msg}), (404 if 'not found' in msg else 400)
    return jsonify({'ok': True, 'message': msg}), 200


@template_studio_blueprint.route('/<string:uuid>/purge', methods=['POST'])
@require_permission('admin_only')
def purge_page(uuid):
    ok, msg = hard_delete_page_core(uuid)
    if not ok:
        return jsonify({'ok': False, 'message': msg}), (404 if 'not found' in msg else 400)
    return jsonify({'ok': True, 'message': msg}), 200
