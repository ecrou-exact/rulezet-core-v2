from flask import request
from flask_restx import Namespace, Resource
from sqlalchemy import or_

from .. import db
from ..core.db_class.log import Log
from ..core.utils.decorators import api_require_permission
from ..core.utils.logger import log_action

log_ns = Namespace('log', description='Application logs — admin only')

# ── Allowed sort columns ────────────────────────────────────────────────────────
_ALLOWED_SORTS = {'id', 'created_at', 'category', 'level', 'action'}


@log_ns.route('/')
class LogList(Resource):
    """Paginated, filtered, sorted list of logs."""
    method_decorators = [api_require_permission("logs.view")]

    def get(self):
        # ── Query params ────────────────────────────────────────────────────────
        try:
            page     = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(1, int(request.args.get('per_page', 25))))
        except (TypeError, ValueError):
            page, per_page = 1, 25

        search   = (request.args.get('search') or '').strip()
        category = (request.args.get('category') or '').strip()
        level    = (request.args.get('level') or '').strip()
        sort_key = request.args.get('sort', 'created_at')
        sort_dir = request.args.get('dir', 'desc')

        # actor_id filter — for user detail page
        actor_id_raw = request.args.get('actor_id')
        actor_id = None
        if actor_id_raw:
            try:
                actor_id = int(actor_id_raw)
            except (TypeError, ValueError):
                pass

        if sort_key not in _ALLOWED_SORTS:
            sort_key = 'created_at'
        if sort_dir not in ('asc', 'desc'):
            sort_dir = 'desc'

        # ── Build query ─────────────────────────────────────────────────────────
        q = db.session.query(Log)

        if search:
            like = f'%{search}%'
            q = q.filter(or_(
                Log.title.ilike(like),
                Log.action.ilike(like),
                Log.description.ilike(like),
            ))

        if category:
            q = q.filter(Log.category == category)

        if level:
            q = q.filter(Log.level == level)

        if actor_id is not None:
            q = q.filter(Log.actor_id == actor_id)

        sort_col = getattr(Log, sort_key)
        q = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())

        total       = q.count()
        total_pages = max(1, (total + per_page - 1) // per_page)
        page        = min(page, total_pages)
        logs        = q.offset((page - 1) * per_page).limit(per_page).all()

        return {
            'items':       [l.to_json() for l in logs],
            'total':       total,
            'page':        page,
            'per_page':    per_page,
            'total_pages': total_pages,
        }, 200


@log_ns.route('/<string:log_uuid>')
class LogDetail(Resource):
    """Delete a single log entry by UUID."""
    method_decorators = [api_require_permission("logs.delete")]

    def delete(self, log_uuid):
        log = Log.query.filter_by(uuid=log_uuid).first()
        if not log:
            return {'message': 'Log not found'}, 404
        db.session.delete(log)
        db.session.commit()
        log_action("Log entry deleted", "delete_log", category="api", level="warning",
                   object_type="log", object_id=log_uuid, is_public=False,
                   meta={"log_uuid": log_uuid})
        return {'message': 'Log deleted'}, 200


@log_ns.route('/bulk-delete')
class LogBulkDelete(Resource):
    """Delete multiple log entries by UUID list."""
    method_decorators = [api_require_permission("logs.delete")]

    def post(self):
        data = request.get_json(silent=True) or {}
        uuids = data.get('uuids', [])
        if not uuids or not isinstance(uuids, list):
            return {'message': 'No uuids provided'}, 400

        deleted = Log.query.filter(Log.uuid.in_(uuids)).delete(
            synchronize_session=False
        )
        db.session.commit()
        log_action("Bulk log entries deleted", "bulk_delete_log", category="api", level="warning",
                   object_type="log", is_public=False,
                   meta={"count": deleted})
        return {'message': f'Deleted {deleted} log(s)'}, 200
