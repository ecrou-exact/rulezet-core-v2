def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


# ── HTML route ────────────────────────────────────────────────────────────────

def test_settings_requires_login(client):
    res = client.get('/admin/settings')
    assert res.status_code == 302


def test_settings_requires_admin(client):
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/admin/settings')
    assert res.status_code == 403


def test_settings_read_only_forbidden(client):
    login_as(client, 'read@read.read', 'read')
    res = client.get('/admin/settings')
    assert res.status_code == 403


def test_settings_as_admin(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/settings')
    assert res.status_code == 200


def test_settings_trailing_slash(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/admin/settings/')
    assert res.status_code == 200


# ── API: system info ─────────────────────────────────────────────────────────

def test_api_system_info_admin(client):
    res = client.get('/api/site-settings/system',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'python_version' in data
    assert 'flask_version' in data
    assert 'platform' in data
    assert 'debug_mode' in data
    assert 'db_uri' in data


def test_api_system_info_forbidden_non_admin(client):
    res = client.get('/api/site-settings/system',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_system_info_forbidden_anon(client):
    res = client.get('/api/site-settings/system')
    assert res.status_code == 403


# ── API: SMTP config ─────────────────────────────────────────────────────────

def test_api_smtp_get_admin(client):
    res = client.get('/api/site-settings/smtp',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'smtp_host' in data
    assert 'smtp_port' in data
    assert 'smtp_user' in data
    assert 'smtp_use_tls' in data
    assert 'smtp_configured' in data
    assert 'smtp_password' not in data  # password must never be returned


def test_api_smtp_get_forbidden(client):
    res = client.get('/api/site-settings/smtp',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_smtp_post_admin(client):
    res = client.post('/api/site-settings/smtp',
        headers={'X-API-KEY': 'admin_api_key', 'Content-Type': 'application/json'},
        json={'smtp_host': 'smtp.test.com', 'smtp_port': '587', 'smtp_user': 'test@test.com'})
    assert res.status_code == 200


def test_api_smtp_post_forbidden(client):
    res = client.post('/api/site-settings/smtp',
        headers={'X-API-KEY': 'editor_api_key', 'Content-Type': 'application/json'},
        json={'smtp_host': 'smtp.test.com'})
    assert res.status_code == 403


# ── API: session key ─────────────────────────────────────────────────────────

def test_api_session_key_regen_admin(client):
    res = client.post('/api/site-settings/session-key',
        headers={'X-API-KEY': 'admin_api_key', 'Content-Type': 'application/json'},
        json={})
    assert res.status_code == 200
    data = res.get_json()
    assert 'message' in data


def test_api_session_key_regen_forbidden(client):
    res = client.post('/api/site-settings/session-key',
        headers={'X-API-KEY': 'editor_api_key', 'Content-Type': 'application/json'},
        json={})
    assert res.status_code == 403


# ── Email verification flow ───────────────────────────────────────────────────

def test_register_without_verification(client):
    """When email_verification_enabled=0 (default), register → immediate login redirect."""
    res = client.post('/account/register', data={
        'first_name': 'Test', 'last_name': 'User',
        'email': 'new@test.com', 'password': 'Password1!',
        'confirm_password': 'Password1!',
    }, follow_redirects=False)
    # Should redirect to account.index (logged in), not verify
    assert res.status_code in (200, 302)
    if res.status_code == 302:
        assert 'verify' not in res.headers.get('Location', '')


def test_verify_page_no_session(client):
    """GET /account/verify without pending session → redirect to register."""
    res = client.get('/account/verify', follow_redirects=False)
    assert res.status_code == 302


def test_verify_with_correct_code(client, app):
    """Correct code marks user verified and logs them in."""
    import os
    from datetime import datetime, timedelta
    from app.core.db_class.site_config import set_site_value
    from app.core.db_class.user import User
    from app import db

    with app.app_context():
        set_site_value('email_verification_enabled', '1')

    with client.session_transaction() as sess:
        # Manually insert a pending user
        pass

    with app.app_context():
        from app.core.utils.utils import generate_api_key
        u = User(
            first_name='Verify', last_name='Me',
            email='verify@test.com', password='Password1!',
            role_id=3,
            api_key=generate_api_key(),
            is_verified=False,
            verification_token='123456',
            verification_expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess['pending_verification_user_id'] = uid

    res = client.post('/account/verify',
        data={'code': '123456'}, follow_redirects=False)
    assert res.status_code == 302

    with app.app_context():
        u = User.query.get(uid)
        assert u is not None
        assert u.is_verified is True
        assert u.verification_token is None

    with app.app_context():
        set_site_value('email_verification_enabled', '0')


def test_verify_with_wrong_code(client, app):
    """Wrong code shows error and does not verify user."""
    from datetime import datetime, timedelta
    from app.core.db_class.user import User
    from app import db

    with app.app_context():
        from app.core.utils.utils import generate_api_key
        u = User(
            first_name='Bad', last_name='Code',
            email='badcode@test.com', password='Password1!',
            role_id=3,
            api_key=generate_api_key(),
            is_verified=False,
            verification_token='654321',
            verification_expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess['pending_verification_user_id'] = uid

    res = client.post('/account/verify',
        data={'code': '000000'}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        u = User.query.get(uid)
        assert u.is_verified is False


def test_verify_expired_code_deletes_user(client, app):
    """Expired code deletes the user and redirects to register."""
    from datetime import datetime, timedelta
    from app.core.db_class.user import User
    from app import db

    with app.app_context():
        from app.core.utils.utils import generate_api_key
        u = User(
            first_name='Exp', last_name='Ired',
            email='expired@test.com', password='Password1!',
            role_id=3,
            api_key=generate_api_key(),
            is_verified=False,
            verification_token='999999',
            verification_expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess['pending_verification_user_id'] = uid

    res = client.get('/account/verify', follow_redirects=False)
    assert res.status_code == 302

    with app.app_context():
        u = User.query.get(uid)
        assert u is None


# ── email_verification toggle via admin API ───────────────────────────────────

def test_toggle_email_verification(client):
    res = client.post('/api/admin/site-config',
        headers={'X-API-KEY': 'admin_api_key', 'Content-Type': 'application/json'},
        json={'key': 'email_verification_enabled', 'value': True})
    assert res.status_code == 200
    data = res.get_json()
    assert data['key'] == 'email_verification_enabled'

    # Disable again
    res2 = client.post('/api/admin/site-config',
        headers={'X-API-KEY': 'admin_api_key', 'Content-Type': 'application/json'},
        json={'key': 'email_verification_enabled', 'value': False})
    assert res2.status_code == 200


def test_toggle_email_verification_forbidden(client):
    res = client.post('/api/admin/site-config',
        headers={'X-API-KEY': 'editor_api_key', 'Content-Type': 'application/json'},
        json={'key': 'email_verification_enabled', 'value': True})
    assert res.status_code == 403
