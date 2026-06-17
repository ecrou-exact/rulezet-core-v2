"""Tests for the background jobs system.

Covers:
- HTML routes: /jobs/, /jobs/<uuid>
- API endpoints: list, create, get, delete, cancel, pause, resume, retry, bulk
- Role boundaries: admin/editor/read-only/anonymous
- Workflow: create → cancel → retry → delete
"""
import pytest
from app import db
from app.core.db_class.job import Job
from app.core.utils.job_runner import register_handler, _HANDLERS


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def register_test_handler():
    """Register a no-op handler for testing."""
    key = 'test.noop'
    _HANDLERS[key] = lambda ctx, meta: {'done': True}
    yield
    _HANDLERS.pop(key, None)


def _make_job(app, status='pending', created_by=None):
    with app.app_context():
        job = Job(
            type='test.noop',
            title='Test Job',
            status=status,
            created_by=created_by,
        )
        db.session.add(job)
        db.session.commit()
        return job.uuid


# ── HTML routes ───────────────────────────────────────────────────────────────

class TestJobsHTML:

    def test_list_redirects_anonymous(self, client):
        r = client.get('/jobs/')
        assert r.status_code == 302
        assert '/account/login' in r.headers['Location']

    def test_list_forbidden_no_permission(self, client):
        client.post('/account/login', data={'email': 'read@read.read', 'password': 'read'}, follow_redirects=True)
        r = client.get('/jobs/')
        assert r.status_code == 403

    def test_list_accessible_with_manage_perm(self, client):
        client.post('/account/login', data={'email': 'admin@admin.admin', 'password': 'admin'}, follow_redirects=True)
        r = client.get('/jobs/')
        assert r.status_code == 200

    def test_detail_redirects_anonymous(self, client, app):
        uuid = _make_job(app)
        r = client.get(f'/jobs/{uuid}')
        assert r.status_code == 302

    def test_detail_not_found(self, client):
        client.post('/account/login', data={'email': 'admin@admin.admin', 'password': 'admin'}, follow_redirects=True)
        r = client.get('/jobs/00000000-0000-0000-0000-000000000000')
        assert r.status_code == 404

    def test_detail_accessible_admin(self, client, app):
        uuid = _make_job(app)
        client.post('/account/login', data={'email': 'admin@admin.admin', 'password': 'admin'}, follow_redirects=True)
        r = client.get(f'/jobs/{uuid}')
        assert r.status_code == 200


# ── API list ──────────────────────────────────────────────────────────────────

class TestJobsAPIList:

    def test_list_anonymous_forbidden(self, client):
        r = client.get('/api/jobs/')
        assert r.status_code == 403

    def test_list_read_only_forbidden(self, client):
        r = client.get('/api/jobs/', headers={'X-API-KEY': 'read_api_key'})
        assert r.status_code == 403

    def test_list_admin_ok(self, client):
        r = client.get('/api/jobs/', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert 'items' in d and 'total' in d

    def test_list_pagination(self, client, app):
        for _ in range(3):
            _make_job(app)
        r = client.get('/api/jobs/?per_page=2&page=1', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert len(d['items']) <= 2
        assert d['total'] >= 3

    def test_list_status_filter(self, client, app):
        _make_job(app, status='failed')
        r = client.get('/api/jobs/?status=failed', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        for item in d['items']:
            assert item['status'] == 'failed'


# ── API create ────────────────────────────────────────────────────────────────

class TestJobsAPICreate:

    def test_create_admin_ok(self, client):
        r = client.post('/api/jobs/', json={'type': 'test.noop', 'title': 'My Job'},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 201
        d = r.get_json()
        assert d['job']['status'] == 'pending'
        assert d['job']['type']   == 'test.noop'

    def test_create_editor_forbidden(self, client):
        r = client.post('/api/jobs/', json={'type': 'test.noop'},
                        headers={'X-API-KEY': 'editor_api_key'})
        assert r.status_code == 403

    def test_create_unknown_type(self, client):
        r = client.post('/api/jobs/', json={'type': 'nonexistent.type'},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_create_missing_type(self, client):
        r = client.post('/api/jobs/', json={},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400


# ── API get ───────────────────────────────────────────────────────────────────

class TestJobsAPIGet:

    def test_get_not_found(self, client):
        r = client.get('/api/jobs/no-such-uuid', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 404

    def test_get_admin_ok(self, client, app):
        uuid = _make_job(app)
        r = client.get(f'/api/jobs/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert d['uuid'] == uuid
        assert 'logs' in d


# ── API delete ────────────────────────────────────────────────────────────────

class TestJobsAPIDelete:

    def test_delete_admin_ok(self, client, app):
        uuid = _make_job(app)
        r = client.delete(f'/api/jobs/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200

    def test_delete_editor_forbidden(self, client, app):
        uuid = _make_job(app)
        r = client.delete(f'/api/jobs/{uuid}', headers={'X-API-KEY': 'editor_api_key'})
        assert r.status_code == 403

    def test_cannot_delete_running(self, client, app):
        uuid = _make_job(app, status='running')
        r = client.delete(f'/api/jobs/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400


# ── API actions ───────────────────────────────────────────────────────────────

class TestJobsAPIActions:

    def test_cancel_pending(self, client, app):
        uuid = _make_job(app, status='pending')
        r = client.post(f'/api/jobs/{uuid}/cancel', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        r2 = client.get(f'/api/jobs/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
        assert r2.get_json()['status'] == 'cancelled'

    def test_cancel_running(self, client, app):
        uuid = _make_job(app, status='running')
        r = client.post(f'/api/jobs/{uuid}/cancel', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200

    def test_cancel_completed_fails(self, client, app):
        uuid = _make_job(app, status='completed')
        r = client.post(f'/api/jobs/{uuid}/cancel', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_pause_running(self, client, app):
        uuid = _make_job(app, status='running')
        r = client.post(f'/api/jobs/{uuid}/pause', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        assert r.get_json()['message'] == 'Job paused'

    def test_pause_non_running_fails(self, client, app):
        uuid = _make_job(app, status='pending')
        r = client.post(f'/api/jobs/{uuid}/pause', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_resume_paused(self, client, app):
        uuid = _make_job(app, status='paused')
        r = client.post(f'/api/jobs/{uuid}/resume', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        assert r.get_json()['message'] == 'Job resumed'

    def test_resume_non_paused_fails(self, client, app):
        uuid = _make_job(app, status='running')
        r = client.post(f'/api/jobs/{uuid}/resume', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_retry_failed(self, client, app):
        uuid = _make_job(app, status='failed')
        r = client.post(f'/api/jobs/{uuid}/retry', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 201
        d = r.get_json()
        assert d['job']['status'] == 'pending'
        assert d['job']['uuid']   != uuid

    def test_retry_pending_fails(self, client, app):
        uuid = _make_job(app, status='pending')
        r = client.post(f'/api/jobs/{uuid}/retry', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_editor_cannot_manage(self, client, app):
        uuid = _make_job(app, status='pending')
        r = client.post(f'/api/jobs/{uuid}/cancel', headers={'X-API-KEY': 'editor_api_key'})
        assert r.status_code == 403


# ── API bulk ──────────────────────────────────────────────────────────────────

class TestJobsAPIBulk:

    def test_bulk_cancel(self, client, app):
        u1 = _make_job(app, status='pending')
        u2 = _make_job(app, status='running')
        r = client.post('/api/jobs/bulk', json={'action': 'cancel', 'uuids': [u1, u2]},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert d['success'] == 2

    def test_bulk_delete(self, client, app):
        u1 = _make_job(app, status='completed')
        u2 = _make_job(app, status='failed')
        r = client.post('/api/jobs/bulk', json={'action': 'delete', 'uuids': [u1, u2]},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert d['success'] == 2

    def test_bulk_invalid_action(self, client):
        r = client.post('/api/jobs/bulk', json={'action': 'restart', 'uuids': []},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_bulk_empty_uuids(self, client):
        r = client.post('/api/jobs/bulk', json={'action': 'delete', 'uuids': []},
                        headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 400

    def test_bulk_read_only_forbidden(self, client):
        r = client.post('/api/jobs/bulk', json={'action': 'delete', 'uuids': ['x']},
                        headers={'X-API-KEY': 'read_api_key'})
        assert r.status_code == 403


# ── Types endpoint ────────────────────────────────────────────────────────────

class TestJobsAPITypes:

    def test_types_admin(self, client):
        r = client.get('/api/jobs/types', headers={'X-API-KEY': 'admin_api_key'})
        assert r.status_code == 200
        d = r.get_json()
        assert 'types' in d
        assert 'test.noop' in d['types']

    def test_types_read_only_forbidden(self, client):
        r = client.get('/api/jobs/types', headers={'X-API-KEY': 'read_api_key'})
        assert r.status_code == 403
