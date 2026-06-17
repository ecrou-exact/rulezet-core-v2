"""jobs_api.py — REST API for background jobs.

Endpoints:
    GET    /api/jobs/              List jobs (paginated)
    POST   /api/jobs/              Create a job
    GET    /api/jobs/types         List registered handler types
    GET    /api/jobs/<uuid>        Get job detail
    DELETE /api/jobs/<uuid>        Soft-delete a job
    POST   /api/jobs/<uuid>/cancel Cancel a running/pending job
    POST   /api/jobs/<uuid>/pause  Pause a running job
    POST   /api/jobs/<uuid>/resume Resume a paused job
    POST   /api/jobs/<uuid>/retry  Retry a failed/cancelled job
    POST   /api/jobs/bulk          Bulk actions (cancel, delete)
"""
from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..core.utils.utils import get_user_api
from ..features.jobs.jobs_core import (
    list_jobs_core, get_job_or_none,
    cancel_job_core, pause_job_core, resume_job_core,
    retry_job_core, delete_job_core,
    bulk_cancel_jobs_core, bulk_delete_jobs_core,
)

jobs_ns = Namespace('jobs', description='Background jobs management')


def _resolve_user():
    """Return the active user from API key or session."""
    api_key = request.headers.get('X-API-KEY')
    if api_key:
        return get_user_api(api_key)
    return current_user if current_user.is_authenticated else None


def _current_user_id():
    user = _resolve_user()
    return user.id if user else None


def _is_admin():
    user = _resolve_user()
    return user is not None and user.is_admin()


def _can_access_job(job) -> bool:
    """Admin can access any job; others can only access their own."""
    if _is_admin():
        return True
    return job.created_by == _current_user_id()


@jobs_ns.route('/')
class JobListResource(Resource):
    method_decorators = [api_require_permission('jobs.view')]

    def get(self):
        """
        List jobs with pagination, search, sort, and status filter.

        Query params:
        - page (int, default 1)
        - per_page (int, default 10, max 100)
        - search (str)
        - sort (str: created_at|title|type|status|progress, default created_at)
        - dir (str: asc|desc, default desc)
        - status (str: pending|running|paused|completed|failed|cancelled)
        """
        page        = max(1, int(request.args.get('page', 1)))
        per_page    = min(100, max(1, int(request.args.get('per_page', 10))))
        search      = request.args.get('search', '')
        sort        = request.args.get('sort', 'created_at')
        direction   = request.args.get('dir', 'desc')
        status_f    = request.args.get('status', '')
        admin_view  = _is_admin()

        if sort not in ('created_at', 'title', 'type', 'status', 'progress', 'started_at', 'finished_at'):
            sort = 'created_at'

        items, total, total_pages = list_jobs_core(
            page=page, per_page=per_page, search=search,
            sort=sort, direction=direction, status_filter=status_f,
            admin_view=admin_view, user_id=_current_user_id(),
        )
        return {
            'items':       [j.to_json() for j in items],
            'total':       total,
            'total_pages': total_pages,
        }, 200

    def post(self):
        """
        Create and enqueue a new job.

        Body:
        - type (str, required): registered handler key
        - title (str, optional): display name
        - meta (dict, optional): data passed to the handler
        """
        if not _is_admin():
            return {'message': 'Admin only'}, 403
        data = request.json or {}
        type_key = (data.get('type') or '').strip()
        if not type_key:
            return {'message': "'type' is required"}, 400

        from ..core.utils.job_runner import get_handler, enqueue_job
        if not get_handler(type_key):
            return {'message': f"No handler registered for type '{type_key}'"}, 400

        title = (data.get('title') or '').strip() or type_key.replace('.', ' ').replace('_', ' ').title()
        meta  = data.get('meta') or {}
        job   = enqueue_job(type_key, title=title, meta=meta, user_id=_current_user_id())
        return {'message': 'Job queued', 'job': job.to_json()}, 201


@jobs_ns.route('/types')
class JobTypesResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def get(self):
        """List all registered job handler type keys."""
        from ..core.utils.job_runner import registered_types
        return {'types': registered_types()}, 200


@jobs_ns.route('/<string:uuid>')
class JobResource(Resource):
    method_decorators = [api_require_permission('jobs.view')]

    def get(self, uuid):
        """Get full job detail including logs, progress, and result."""
        job = get_job_or_none(uuid)
        if not job:
            return {'message': 'Job not found'}, 404
        if not _can_access_job(job):
            return {'message': 'Access denied'}, 403
        return job.to_json(), 200

    def delete(self, uuid):
        """Soft-delete a job (cannot delete a running job)."""
        if not _is_admin():
            return {'message': 'Admin only'}, 403
        ok, msg = delete_job_core(uuid, _current_user_id())
        if not ok:
            return {'message': msg}, 400
        return {'message': msg}, 200


@jobs_ns.route('/<string:uuid>/cancel')
class JobCancelResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def post(self, uuid):
        """Cancel a pending, running, or paused job."""
        ok, msg = cancel_job_core(uuid, _current_user_id())
        if not ok:
            return {'message': msg}, 400
        return {'message': msg}, 200


@jobs_ns.route('/<string:uuid>/pause')
class JobPauseResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def post(self, uuid):
        """Pause a running job at its next checkpoint."""
        ok, msg = pause_job_core(uuid, _current_user_id())
        if not ok:
            return {'message': msg}, 400
        return {'message': msg}, 200


@jobs_ns.route('/<string:uuid>/resume')
class JobResumeResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def post(self, uuid):
        """Resume a paused job."""
        ok, msg = resume_job_core(uuid, _current_user_id())
        if not ok:
            return {'message': msg}, 400
        return {'message': msg}, 200


@jobs_ns.route('/<string:uuid>/retry')
class JobRetryResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def post(self, uuid):
        """Retry a failed or cancelled job (creates a new pending job)."""
        new_job, msg = retry_job_core(uuid, _current_user_id())
        if not new_job:
            return {'message': msg}, 400
        return {'message': msg, 'job': new_job.to_json()}, 201


@jobs_ns.route('/bulk')
class JobBulkResource(Resource):
    method_decorators = [api_require_permission('jobs.manage')]

    def post(self):
        """
        Bulk action on multiple jobs.

        Body:
        - action (str): 'cancel' | 'delete'
        - uuids (list[str]): list of job UUIDs
        """
        data   = request.json or {}
        action = (data.get('action') or '').strip()
        uuids  = data.get('uuids') or []

        if action not in ('cancel', 'delete'):
            return {'message': "action must be 'cancel' or 'delete'"}, 400
        if not isinstance(uuids, list) or not uuids:
            return {'message': 'uuids must be a non-empty list'}, 400

        uid = _current_user_id()
        if action == 'cancel':
            ok, fail = bulk_cancel_jobs_core(uuids, uid)
        else:
            ok, fail = bulk_delete_jobs_core(uuids, uid)

        return {
            'message':  f"{ok} job(s) {action}d" + (f", {fail} failed" if fail else ""),
            'success':  ok,
            'failed':   fail,
        }, 200
