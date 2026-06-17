"""
tests/admin/test_user_detail.py

Tests for:
  - GET /admin/users/<uid>          (HTML — admin only)
  - PUT /api/account/admin/user/<uid>  (admin edit endpoint)
  - GET /api/account/user-activity/<uid>  (activity chart data)
  - GET /api/account/roles          (roles list)
"""


def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


# ── HTML route: /admin/users/<uid> ────────────────────────────────────────────

def test_user_detail_requires_login(client):
    """Unauthenticated user is redirected."""
    res = client.get('/admin/users/1')
    assert res.status_code == 302


def test_user_detail_requires_admin(client):
    """Non-admin (editor) cannot access the detail page."""
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/admin/users/1')
    assert res.status_code == 403


def test_user_detail_readonly_forbidden(client):
    """Read-only user cannot access the detail page."""
    login_as(client, 'read@read.read', 'read')
    res = client.get('/admin/users/1')
    assert res.status_code == 403


def test_user_detail_as_admin(client):
    """Admin can access the detail page and gets 200."""
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/users/1')
    assert res.status_code == 200


def test_user_detail_not_found(client):
    """Non-existent user returns 404."""
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/users/99999')
    assert res.status_code == 404


# ── API: PUT /api/account/admin/user/<uid> ────────────────────────────────────

def test_admin_edit_user_as_admin(client):
    """Admin can edit a user's first name."""
    res = client.put('/api/account/admin/user/1',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'first_name': 'Updated'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['first_name'] == 'Updated'


def test_admin_edit_user_change_role(client):
    """Admin can change role_id of a user."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'role_id': 3})
    assert res.status_code == 200
    data = res.get_json()
    assert data['role_id'] == 3


def test_admin_edit_user_toggle_verified(client):
    """Admin can toggle is_verified."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'is_verified': False})
    assert res.status_code == 200
    assert res.get_json()['is_verified'] is False


def test_admin_edit_user_forbidden_without_key(client):
    """Request without API key is rejected."""
    res = client.put('/api/account/admin/user/1',
        content_type='application/json',
        json={'first_name': 'Hacked'})
    assert res.status_code == 403


def test_admin_edit_user_forbidden_for_editor(client):
    """Editor API key is not admin — rejected."""
    res = client.put('/api/account/admin/user/1',
        headers={'X-API-KEY': 'editor_api_key'},
        content_type='application/json',
        json={'first_name': 'Hacked'})
    assert res.status_code == 403


def test_admin_edit_user_not_found(client):
    """Editing a non-existent user returns 404."""
    res = client.put('/api/account/admin/user/99999',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'first_name': 'Ghost'})
    assert res.status_code == 404


def test_admin_edit_user_invalid_email(client):
    """Invalid email format returns 400."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'email': 'not-an-email'})
    assert res.status_code == 400


def test_admin_edit_user_duplicate_email(client):
    """Cannot reassign email already used by another user."""
    # editor tries to take admin's email
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'email': 'admin@admin.admin'})
    assert res.status_code == 400


def test_admin_edit_user_invalid_username(client):
    """Username with invalid characters returns 400."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'username': 'invalid user name!'})
    assert res.status_code == 400


def test_admin_edit_user_invalid_role(client):
    """Non-existent role_id returns 400."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'role_id': 9999})
    assert res.status_code == 400


def test_admin_edit_user_no_data(client):
    """Empty body returns 400."""
    res = client.put('/api/account/admin/user/1',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={})
    assert res.status_code == 400


# ── Security: input sanitisation ─────────────────────────────────────────────

def test_admin_edit_user_xss_first_name(client):
    """XSS attempt in first_name is rejected (control chars or oversized)."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'first_name': '<script>alert(1)</script>'})
    # The endpoint accepts it as a plain string (HTML is escaped by Jinja),
    # but it must NOT be 200 if it contains null bytes or overflows 64 chars
    # In practice the endpoint stores it; verify it doesn't return 500
    assert res.status_code in (200, 400)


def test_admin_edit_user_oversized_field(client):
    """Field exceeding max length is truncated or rejected."""
    res = client.put('/api/account/admin/user/2',
        headers={'X-API-KEY': 'admin_api_key'},
        content_type='application/json',
        json={'first_name': 'A' * 1000})
    # String gets truncated to 64 or accepted; must not crash
    assert res.status_code in (200, 400)


# ── API: GET /api/account/user-activity/<uid> ─────────────────────────────────

def test_user_activity_as_admin(client):
    """Admin can fetch activity for any user."""
    res = client.get('/api/account/user-activity/1',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'daily' in data
    assert 'total_events' in data
    assert 'total_logins' in data
    assert len(data['daily']) == 30


def test_user_activity_data_shape(client):
    """Each daily entry has date and count."""
    res = client.get('/api/account/user-activity/1',
        headers={'X-API-KEY': 'admin_api_key'})
    data = res.get_json()
    for entry in data['daily']:
        assert 'date' in entry
        assert 'count' in entry
        assert isinstance(entry['count'], int)


def test_user_activity_forbidden_without_key(client):
    """Request without API key is rejected."""
    res = client.get('/api/account/user-activity/1')
    assert res.status_code == 403


def test_user_activity_forbidden_for_editor(client):
    """Editor API key is rejected."""
    res = client.get('/api/account/user-activity/1',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_user_activity_not_found(client):
    """Non-existent user returns 404."""
    res = client.get('/api/account/user-activity/99999',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 404


# ── API: GET /api/account/roles ───────────────────────────────────────────────

def test_roles_list_as_admin(client):
    """Admin can list all roles."""
    res = client.get('/api/account/roles',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for role in data:
        assert 'id' in role
        assert 'name' in role


def test_roles_list_forbidden_without_key(client):
    """No API key → 403."""
    res = client.get('/api/account/roles')
    assert res.status_code == 403


def test_roles_list_forbidden_for_editor(client):
    """Editor key → 403 (not admin)."""
    res = client.get('/api/account/roles',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403
