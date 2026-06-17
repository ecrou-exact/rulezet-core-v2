"""connectors_api.py — REST API for Connectors."""
from flask import request
from flask_login import current_user
from flask_restx import Namespace, Resource

from ..core.utils.decorators import api_require_permission
from ..core.utils.utils import get_user_api
from ..features.connectors.connectors_core import (
    list_connectors, get_connector_by_uuid,
    create_connector_core, update_connector_core, delete_connector_core,
    enqueue_connector_test, enqueue_connector_sync,
    receive_push_core,
)

connectors_ns = Namespace('connectors', description='Connector management')


def _get_caller():
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

@connectors_ns.route('/')
class ConnectorList(Resource):

    @api_require_permission('connectors.view')
    def get(self):
        """List connectors with pagination and search."""
        user, _ = _get_caller()
        status    = request.args.get('status')
        page      = max(1, int(request.args.get('page', 1)))
        per_page  = min(200, max(1, int(request.args.get('per_page', 25))))
        search    = request.args.get('search', '').strip()
        sort      = request.args.get('sort', 'name')
        direction = request.args.get('dir', 'asc')

        items, total, total_pages = list_connectors(
            status=status, page=page, per_page=per_page,
            search=search, sort=sort, direction=direction,
        )
        return {
            'items':       [c.to_json() for c in items],
            'total':       total,
            'total_pages': total_pages,
        }, 200

    @api_require_permission('connectors.manage')
    def post(self):
        """Create a connector."""
        user, _ = _get_caller()
        data = request.get_json() or {}
        connector, msg = create_connector_core(data, user.id)
        if not connector:
            return {'message': msg}, 400
        return connector.to_json(include_key=True), 201


# ── Single connector ──────────────────────────────────────────────────────────

@connectors_ns.route('/<string:uuid>')
class ConnectorItem(Resource):

    @api_require_permission('connectors.view')
    def get(self, uuid):
        connector = get_connector_by_uuid(uuid)
        if not connector:
            return {'message': 'Connector not found.'}, 404
        return connector.to_json(), 200

    @api_require_permission('connectors.manage')
    def put(self, uuid):
        data = request.get_json() or {}
        connector, msg = update_connector_core(uuid, data, _get_caller()[0].id)
        if not connector:
            return {'message': msg}, 400
        return connector.to_json(), 200

    @api_require_permission('connectors.manage')
    def delete(self, uuid):
        user, _ = _get_caller()
        ok, msg = delete_connector_core(uuid, user.id)
        if not ok:
            return {'message': msg}, 404
        return {'message': msg}, 200


# ── Test / Sync jobs ──────────────────────────────────────────────────────────

@connectors_ns.route('/<string:uuid>/test')
class ConnectorTest(Resource):

    @api_require_permission('connectors.manage')
    def post(self, uuid):
        """Enqueue a connectivity test job."""
        user, _ = _get_caller()
        connector = get_connector_by_uuid(uuid)
        if not connector:
            return {'message': 'Connector not found.'}, 404
        if not connector.outgoing_key:
            return {'message': 'No outgoing key configured — cannot test.'}, 400
        job = enqueue_connector_test(uuid, user.id)
        if not job:
            return {'message': 'Failed to enqueue test.'}, 500
        return {'message': 'Test started.', 'job_uuid': job.uuid}, 202


@connectors_ns.route('/<string:uuid>/sync')
class ConnectorSync(Resource):

    @api_require_permission('connectors.manage')
    def post(self, uuid):
        """Enqueue a sync job."""
        user, _ = _get_caller()
        connector = get_connector_by_uuid(uuid)
        if not connector:
            return {'message': 'Connector not found.'}, 404
        if connector.direction == 'push':
            return {'message': 'Push-only connector: remote initiates sync.'}, 400
        if not connector.outgoing_key:
            return {'message': 'No outgoing key configured — cannot sync.'}, 400
        job = enqueue_connector_sync(uuid, user.id)
        if not job:
            return {'message': 'Failed to enqueue sync.'}, 500
        return {'message': 'Sync started.', 'job_uuid': job.uuid}, 202


# ── Incoming push (no normal auth — incoming_key IS the token) ────────────────

@connectors_ns.route('/push/<string:key>')
class ConnectorIncoming(Resource):

    def post(self, key):
        """Receive a data push from a remote connector."""
        data = request.get_json() or {}
        count, msg = receive_push_core(key, data)
        if count == -1:
            return {'message': msg}, 404
        return {'message': msg, 'count': count}, 200
