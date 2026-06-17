"""
tests/admin/test_logs.py — Tests for the application log system.

Covers:
  - HTML route access control
  - API list endpoint (structure, pagination, filtering, sorting)
  - API single-delete endpoint
  - API bulk-delete endpoint
  - Access control by role (admin / editor / anonymous)
"""

from app.core.db_class.log import Log


# ── Helpers ───────────────────────────────────────────────────────────────────

def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


def _create_log(app, **kwargs):
    """Insert a log directly into the test DB and return it."""
    from app import db
    defaults = dict(
        title='Test log',
        action='test_action',
        category='system',
        level='info',
    )
    defaults.update(kwargs)
    with app.app_context():
        log = Log(**defaults)
        db.session.add(log)
        db.session.commit()
        return log.uuid


# ── HTML routes ───────────────────────────────────────────────────────────────

def test_logs_page_requires_login(client):
    """Unauthenticated request is redirected to login."""
    res = client.get('/admin/logs')
    assert res.status_code == 302


def test_logs_page_requires_admin(client):
    """Non-admin user (editor) cannot access the logs page."""
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/admin/logs')
    assert res.status_code == 403


def test_logs_page_requires_admin_readonly(client):
    """Read-only user cannot access the logs page."""
    login_as(client, 'read@read.read', 'read')
    res = client.get('/admin/logs')
    assert res.status_code == 403


def test_logs_page_as_admin(client):
    """Admin can access the logs page and gets 200."""
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/logs')
    assert res.status_code == 200


# ── API: list logs ────────────────────────────────────────────────────────────

def test_api_list_logs_forbidden_no_key(client):
    """Request without API key is rejected with 403."""
    res = client.get('/api/log/')
    assert res.status_code == 403


def test_api_list_logs_forbidden_editor(client):
    """Editor API key is rejected (not admin)."""
    res = client.get('/api/log/', headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_list_logs_forbidden_readonly(client):
    """Read-only API key is rejected."""
    res = client.get('/api/log/', headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


def test_api_list_logs_as_admin(app, client):
    """Admin API key can list logs and gets the expected JSON structure."""
    _create_log(app, title='Visible log', action='test', category='system', level='info')

    res = client.get('/api/log/', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'page' in data
    assert 'per_page' in data
    assert 'total_pages' in data
    assert isinstance(data['items'], list)
    assert data['total'] >= 1


def test_api_list_logs_item_shape(app, client):
    """Each log item has the required fields."""
    _create_log(app, title='Shape test', action='shape', category='api', level='success')

    res = client.get('/api/log/', headers={'X-API-KEY': 'admin_api_key'})
    data = res.get_json()
    required = {'id', 'uuid', 'title', 'action', 'category', 'level', 'created_at', 'is_public'}
    for item in data['items']:
        for field in required:
            assert field in item, f"Missing field: {field}"


def test_api_list_logs_pagination(app, client):
    """per_page param is respected."""
    for i in range(5):
        _create_log(app, title=f'Log {i}', action='paginate', category='system', level='info')

    res = client.get('/api/log/?per_page=2', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['per_page'] == 2
    assert len(data['items']) <= 2


def test_api_list_logs_search(app, client):
    """Search filter works on title."""
    _create_log(app, title='Unique findable entry XYZ', action='search_test', category='user', level='info')

    res = client.get('/api/log/?search=XYZ', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['total'] >= 1
    for item in data['items']:
        assert 'xyz' in (item.get('title') or '').lower() or \
               'xyz' in (item.get('action') or '').lower(), \
               f"Item does not match search 'XYZ': {item}"


def test_api_list_logs_filter_category(app, client):
    """category filter returns only matching logs."""
    _create_log(app, title='Security event', action='intrusion', category='security', level='error')
    _create_log(app, title='System event', action='boot', category='system', level='info')

    res = client.get('/api/log/?category=security', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    for item in data['items']:
        assert item['category'] == 'security'


def test_api_list_logs_filter_level(app, client):
    """level filter returns only matching logs."""
    _create_log(app, title='Error event', action='crash', category='system', level='error')
    _create_log(app, title='Info event', action='start', category='system', level='info')

    res = client.get('/api/log/?level=error', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    for item in data['items']:
        assert item['level'] == 'error'


def test_api_list_logs_sort_asc(app, client):
    """Sort by id ascending returns items in order."""
    for i in range(3):
        _create_log(app, title=f'Sort log {i}', action='sort', category='system', level='info')

    res = client.get('/api/log/?sort=id&dir=asc', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    items = res.get_json()['items']
    ids = [i['id'] for i in items]
    assert ids == sorted(ids)


def test_api_list_logs_sort_desc(app, client):
    """Sort by id descending returns items in reverse order."""
    for i in range(3):
        _create_log(app, title=f'Sort desc {i}', action='sort_desc', category='system', level='info')

    res = client.get('/api/log/?sort=id&dir=desc', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    items = res.get_json()['items']
    ids = [i['id'] for i in items]
    assert ids == sorted(ids, reverse=True)


def test_api_list_logs_invalid_sort_ignored(client):
    """Invalid sort key falls back gracefully — no 500."""
    res = client.get('/api/log/?sort=__bad__&dir=asc', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200


# ── API: delete single log ────────────────────────────────────────────────────

def test_api_delete_log_forbidden(app, client):
    """Non-admin cannot delete a log."""
    uuid = _create_log(app)
    res = client.delete(f'/api/log/{uuid}', headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_delete_log_not_found(client):
    """Deleting a non-existent UUID returns 404."""
    res = client.delete('/api/log/00000000-0000-0000-0000-000000000000',
                        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 404


def test_api_delete_log_as_admin(app, client):
    """Admin can delete a log by UUID."""
    uuid = _create_log(app, title='To be deleted', action='delete_me', category='system', level='info')

    res = client.delete(f'/api/log/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'message' in data

    # Confirm it's gone
    res2 = client.delete(f'/api/log/{uuid}', headers={'X-API-KEY': 'admin_api_key'})
    assert res2.status_code == 404


# ── API: bulk delete ──────────────────────────────────────────────────────────

def test_api_bulk_delete_forbidden(app, client):
    """Non-admin cannot bulk-delete logs."""
    uuid = _create_log(app)
    res = client.post('/api/log/bulk-delete',
                      json={'uuids': [uuid]},
                      headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_bulk_delete_no_uuids(client):
    """Bulk delete with empty list returns 400."""
    res = client.post('/api/log/bulk-delete',
                      json={'uuids': []},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


def test_api_bulk_delete_as_admin(app, client):
    """Admin can bulk-delete multiple logs."""
    uuid1 = _create_log(app, title='Bulk 1', action='bulk', category='system', level='info')
    uuid2 = _create_log(app, title='Bulk 2', action='bulk', category='system', level='info')

    res = client.post('/api/log/bulk-delete',
                      json={'uuids': [uuid1, uuid2]},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'message' in data

    # Confirm both are gone
    r1 = client.delete(f'/api/log/{uuid1}', headers={'X-API-KEY': 'admin_api_key'})
    r2 = client.delete(f'/api/log/{uuid2}', headers={'X-API-KEY': 'admin_api_key'})
    assert r1.status_code == 404
    assert r2.status_code == 404


# ── log_action integration ────────────────────────────────────────────────────

def test_login_creates_log(app, client):
    """Successful login creates a log entry with action='login'."""
    login_as(client, 'admin@admin.admin', 'admin')

    with app.app_context():
        from app import db
        log = db.session.query(Log).filter_by(action='login').first()
        assert log is not None
        assert log.category == 'user'
        assert log.level == 'success'


def test_failed_login_creates_security_log(app, client):
    """Failed login creates a security log with action='login_failed'."""
    client.post('/account/login',
        data={'email': 'nobody@nowhere.com', 'password': 'wrong'},
        follow_redirects=True)

    with app.app_context():
        from app import db
        log = db.session.query(Log).filter_by(action='login_failed').first()
        assert log is not None
        assert log.category == 'security'
        assert log.level == 'warning'
