def login_as(client, email, password):
    return client.post('/account/login', data={'email': email, 'password': password}, follow_redirects=True)


# ── HTML routes ──────────────────────────────────────────────────────────────

def test_settings_requires_login(client):
    res = client.get('/settings')
    assert res.status_code == 302

def test_settings_as_admin(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/settings')
    assert res.status_code == 200

def test_settings_as_editor(client):
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/settings')
    assert res.status_code == 200


# ── Session-based config update (/config/update) ─────────────────────────────

def test_update_theme(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={'theme': 'dark'})
    assert res.status_code == 200
    assert res.get_json()['config']['theme'] == 'dark'

def test_update_nav_position(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={'nav_position': 'topbar'})
    assert res.status_code == 200
    assert res.get_json()['config']['nav_position'] == 'topbar'

def test_update_sidebar_collapsed(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={'sidebar_collapsed': True})
    assert res.status_code == 200
    assert res.get_json()['config']['sidebar_collapsed'] is True

def test_update_requires_login(client):
    res = client.post('/config/update',
        content_type='application/json',
        json={'theme': 'dark'})
    assert res.status_code == 302  # redirect to login

def test_update_invalid_theme(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={'theme': 'neon'})
    assert res.status_code == 400

def test_update_invalid_nav_position(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={'nav_position': 'bottom'})
    assert res.status_code == 400

def test_update_no_data(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.post('/config/update',
        content_type='application/json',
        json={})
    assert res.status_code == 400

def test_update_as_editor(client):
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.post('/config/update',
        content_type='application/json',
        json={'theme': 'light'})
    assert res.status_code == 200
    assert res.get_json()['config']['theme'] == 'light'


# ── API endpoints (X-API-KEY) still work ─────────────────────────────────────

def test_api_get_config(client):
    res = client.get('/api/config/', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'theme' in data

def test_api_forbidden_without_key(client):
    res = client.get('/api/config/')
    assert res.status_code == 403
