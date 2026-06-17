def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


# ── HTML routes ───────────────────────────────────────────────────────────────

def test_users_requires_login(client):
    """Unauthenticated request is redirected to login."""
    res = client.get('/admin/users')
    assert res.status_code == 302


def test_users_requires_admin(client):
    """Non-admin user (editor) is forbidden."""
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/admin/users')
    assert res.status_code == 403


def test_users_as_admin(client):
    """Admin can access the users page."""
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/users')
    assert res.status_code == 200


def test_users_read_only_forbidden(client):
    """Read-only user cannot access admin users page."""
    login_as(client, 'read@read.read', 'read')
    res = client.get('/admin/users')
    assert res.status_code == 403


# ── API: list users ───────────────────────────────────────────────────────────

def test_api_list_users_as_admin(client):
    """Admin API key can list users and gets correct JSON structure."""
    res = client.get('/api/account/users',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'items' in data
    assert 'total' in data
    assert 'page' in data
    assert 'per_page' in data
    assert 'total_pages' in data
    assert isinstance(data['items'], list)
    assert data['total'] >= 1


def test_api_list_users_items_shape(client):
    """Each user item has the required fields."""
    res = client.get('/api/account/users',
        headers={'X-API-KEY': 'admin_api_key'})
    data = res.get_json()
    required = {'id', 'first_name', 'last_name', 'email', 'role_id',
                'role_name', 'is_admin', 'created_at'}
    for item in data['items']:
        for field in required:
            assert field in item, f"Missing field: {field}"


def test_api_list_users_forbidden_no_key(client):
    """Request without API key is rejected."""
    res = client.get('/api/account/users')
    assert res.status_code == 403


def test_api_list_users_forbidden_editor(client):
    """Editor API key is rejected (not admin)."""
    res = client.get('/api/account/users',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_list_users_forbidden_readonly(client):
    """Read-only API key is rejected."""
    res = client.get('/api/account/users',
        headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


def test_api_list_users_pagination(client):
    """Pagination params are respected."""
    res = client.get('/api/account/users?page=1&per_page=2',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['per_page'] == 2
    assert len(data['items']) <= 2


def test_api_list_users_search(client):
    """Search filters results by email."""
    res = client.get('/api/account/users?search=admin',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['total'] >= 1
    for item in data['items']:
        match = (
            'admin' in (item.get('first_name') or '').lower() or
            'admin' in (item.get('last_name')  or '').lower() or
            'admin' in (item.get('email')      or '').lower() or
            'admin' in (item.get('username')   or '').lower()
        )
        assert match, f"Item does not match search 'admin': {item}"


def test_api_list_users_sort_asc(client):
    """Sort by id ascending returns items in order."""
    res = client.get('/api/account/users?sort=id&dir=asc',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    items = res.get_json()['items']
    ids = [i['id'] for i in items]
    assert ids == sorted(ids)


def test_api_list_users_sort_desc(client):
    """Sort by id descending returns items in reverse order."""
    res = client.get('/api/account/users?sort=id&dir=desc',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    items = res.get_json()['items']
    ids = [i['id'] for i in items]
    assert ids == sorted(ids, reverse=True)


def test_api_list_users_invalid_sort_ignored(client):
    """Invalid sort key falls back to 'id', no error."""
    res = client.get('/api/account/users?sort=password_hash&dir=asc',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200


def test_api_list_users_no_api_key_leak(client):
    """API key must never appear in the user list response."""
    res = client.get('/api/account/users',
        headers={'X-API-KEY': 'admin_api_key'})
    data = res.get_json()
    for item in data['items']:
        assert 'api_key' not in item, "api_key must not be exposed in list"
