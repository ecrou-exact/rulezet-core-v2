"""
tags_api.py — REST API for Tags.
"""
from flask import request
from flask_login import current_user
from flask_restx import Namespace, Resource

from ..core.utils.decorators import api_require_permission
from ..core.utils.utils import get_user_api
from ..core.db_class.tag import Tag
from ..features.tags.tags_core import (
    list_tags, list_tags_paginated, get_tag_by_uuid, create_tag_core, update_tag_core,
    delete_tag_core, bulk_action_core, get_import_sources,
    enqueue_taxonomy_import, enqueue_galaxy_import,
    enqueue_all_taxonomies_import, enqueue_all_galaxies_import,
    get_available_namespaces,
)

tags_ns = Namespace('tags', description='Tag management')


def _get_caller():
    """Return (user, is_admin) for the current request (API key or session)."""
    api_key = request.headers.get('X-API-KEY')
    if api_key:
        user = get_user_api(api_key)
    else:
        user = current_user if current_user.is_authenticated else None
    if not user:
        return None, False
    is_admin = bool(user.role and user.role.admin)
    return user, is_admin


# ── List / Create ─────────────────────────────────────────────────────────────

@tags_ns.route('/')
class TagList(Resource):

    @api_require_permission('tags.view')
    def get(self):
        """List tags with pagination, search, sort, and source filter."""
        user, is_admin = _get_caller()

        source    = request.args.get('source')
        namespace = request.args.get('namespace')
        is_active_str = request.args.get('is_active')
        is_active = None
        if is_active_str == '1':
            is_active = True
        elif is_active_str == '0':
            is_active = False

        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(200, max(1, int(request.args.get('per_page', 25))))
        search   = request.args.get('search', '').strip()
        sort     = request.args.get('sort', 'name')
        direction = request.args.get('dir', 'asc')

        items, total, total_pages = list_tags_paginated(
            source=source, namespace=namespace, is_active=is_active,
            viewer_id=user.id if user else None, is_admin=is_admin,
            page=page, per_page=per_page, search=search,
            sort=sort, direction=direction,
        )
        vid = user.id if user else None
        return {
            'items':       [t.to_json(viewer_id=vid, is_admin=is_admin) for t in items],
            'total':       total,
            'total_pages': total_pages,
        }, 200

    @api_require_permission('tags.manage')
    def post(self):
        """Create a custom tag."""
        user, _ = _get_caller()
        data = request.get_json() or {}
        tag, msg = create_tag_core(data, user.id)
        if not tag:
            return {'message': msg}, 400
        return tag.to_json(), 201


# ── Single tag ────────────────────────────────────────────────────────────────

@tags_ns.route('/<string:uuid>')
class TagItem(Resource):

    @api_require_permission('tags.view')
    def get(self, uuid):
        user, is_admin = _get_caller()
        tag = get_tag_by_uuid(uuid)
        if not tag:
            return {'message': 'Tag not found.'}, 404
        uid = user.id if user else None
        if not tag.is_public and not is_admin and tag.created_by != uid:
            return {'message': 'Not found.'}, 404
        return tag.to_json(viewer_id=uid, is_admin=is_admin), 200

    @api_require_permission('tags.manage')
    def put(self, uuid):
        user, is_admin = _get_caller()
        tag = Tag.query.filter_by(uuid=uuid).first()
        if not tag:
            return {'message': 'Tag not found.'}, 404
        if tag.source == 'custom' and not is_admin and tag.created_by != user.id:
            return {'message': 'Not authorized.'}, 403
        data = request.get_json() or {}
        tag, msg = update_tag_core(uuid, data, user.id)
        if not tag:
            return {'message': msg}, 400
        return tag.to_json(), 200

    @api_require_permission('tags.manage')
    def delete(self, uuid):
        user, is_admin = _get_caller()
        tag = Tag.query.filter_by(uuid=uuid).first()
        if not tag:
            return {'message': 'Tag not found.'}, 404
        if tag.source == 'custom' and not is_admin and tag.created_by != user.id:
            return {'message': 'Not authorized.'}, 403
        ok, msg = delete_tag_core(uuid, user.id)
        if not ok:
            return {'message': msg}, 400
        return {'message': msg}, 200


# ── Bulk actions ──────────────────────────────────────────────────────────────

@tags_ns.route('/bulk')
class TagBulk(Resource):

    @api_require_permission('tags.manage')
    def post(self):
        """Bulk activate / deactivate / delete tags."""
        user, _ = _get_caller()
        data   = request.get_json() or {}
        action = data.get('action')
        uuids  = data.get('uuids', [])
        if action not in ('activate', 'deactivate', 'delete'):
            return {'message': 'Invalid action.'}, 400
        if not uuids:
            return {'message': 'No tags selected.'}, 400
        count, msg = bulk_action_core(action, uuids, user.id)
        return {'message': msg, 'count': count}, 200


# ── Namespaces ────────────────────────────────────────────────────────────────

@tags_ns.route('/namespaces')
class TagNamespaces(Resource):

    @api_require_permission('tags.view')
    def get(self):
        return {'namespaces': get_available_namespaces()}, 200


# ── Import sources metadata ───────────────────────────────────────────────────

@tags_ns.route('/import/sources')
class TagImportSources(Resource):

    @api_require_permission('tags.manage')
    def get(self):
        """List available taxonomy namespaces and galaxy clusters."""
        sources = get_import_sources()
        return {
            'taxonomies': [t['name'] for t in sources['taxonomies']],
            'galaxies':   [g['name'] for g in sources['galaxies']],
        }, 200


# ── Import taxonomy ───────────────────────────────────────────────────────────

@tags_ns.route('/import/taxonomy')
class TagImportTaxonomy(Resource):

    @api_require_permission('tags.manage')
    def post(self):
        """Import a taxonomy namespace (or all). Returns 202 + job uuid."""
        user, _ = _get_caller()
        data      = request.get_json() or {}
        namespace = data.get('namespace', 'ALL')

        if namespace == 'ALL':
            job = enqueue_all_taxonomies_import(user.id)
        else:
            job = enqueue_taxonomy_import(namespace, user.id)

        return {'message': 'Import started.', 'job_uuid': job.uuid}, 202


# ── Import galaxy ─────────────────────────────────────────────────────────────

@tags_ns.route('/import/galaxy')
class TagImportGalaxy(Resource):

    @api_require_permission('tags.manage')
    def post(self):
        """Import a galaxy cluster (or all). Returns 202 + job uuid."""
        user, _ = _get_caller()
        data         = request.get_json() or {}
        cluster_name = data.get('cluster', 'ALL')

        if cluster_name == 'ALL':
            job = enqueue_all_galaxies_import(user.id)
        else:
            job = enqueue_galaxy_import(cluster_name, user.id)

        return {'message': 'Import started.', 'job_uuid': job.uuid}, 202
