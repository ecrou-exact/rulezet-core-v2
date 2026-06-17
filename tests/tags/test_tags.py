"""
test_tags.py — Tests for the Tags feature.

Roles tested:
  admin  → admin@admin.admin   / admin_api_key   (bypasses all perms)
  editor → editor@editor.editor / editor_api_key  (no special perms by default)
  reader → read@read.read      / read_api_key    (read-only)
  anon   → not logged in
"""
import pytest


def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


def _grant_permission(app, role_name, perm_key):
    from app.core.db_class.user import Role, RolePermission
    from app import db
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        if role and not role.has_permission(perm_key):
            rp = RolePermission(role_id=role.id, permission=perm_key)
            db.session.add(rp)
            db.session.commit()


def _create_tag(app, name='tlp:red', color='#FF2B2B', source='taxonomy', is_public=True):
    from app.core.db_class.tag import Tag
    from app import db
    with app.app_context():
        t = Tag(name=name, color=color, source=source, namespace=name.split(':')[0],
                is_public=is_public, is_active=True)
        db.session.add(t)
        db.session.commit()
        return t.uuid


# ── HTML route ────────────────────────────────────────────────────────────────

def test_tags_page_anon_redirect(client):
    res = client.get('/tags/', follow_redirects=False)
    assert res.status_code == 302


def test_tags_page_admin_ok(client):
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/tags/')
    assert res.status_code == 200


def test_tags_page_no_perm_forbidden(client):
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/tags/')
    assert res.status_code == 403


def test_tags_page_with_view_perm(client, app):
    _grant_permission(app, 'Editor', 'tags.view')
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/tags/')
    assert res.status_code == 200


def test_tags_page_reader_no_perm(client):
    login_as(client, 'read@read.read', 'read')
    res = client.get('/tags/')
    assert res.status_code == 403


# ── API GET list ──────────────────────────────────────────────────────────────

def test_api_list_bad_key_403(client):
    res = client.get('/api/tags/', headers={'X-API-KEY': 'bad_key'})
    assert res.status_code == 403


def test_api_list_admin_ok(client):
    res = client.get('/api/tags/', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    d = res.get_json()
    assert 'items' in d
    assert 'total' in d
    assert isinstance(d['items'], list)


def test_api_list_reader_no_perm(client):
    res = client.get('/api/tags/', headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


def test_api_list_editor_with_perm(client, app):
    _grant_permission(app, 'Editor', 'tags.view')
    res = client.get('/api/tags/', headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 200
    assert 'items' in res.get_json()


# ── API POST create ───────────────────────────────────────────────────────────

def test_api_create_admin_ok(client):
    res = client.post('/api/tags/',
        json={'name': 'custom:test', 'color': '#3b82f6', 'source': 'custom'},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 201
    d = res.get_json()
    assert d['name'] == 'custom:test'


def test_api_create_no_perm(client):
    res = client.post('/api/tags/',
        json={'name': 'custom:denied'},
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_create_reader_blocked(client):
    res = client.post('/api/tags/',
        json={'name': 'custom:denied'},
        headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


def test_api_create_with_manage_perm(client, app):
    _grant_permission(app, 'Editor', 'tags.manage')
    res = client.post('/api/tags/',
        json={'name': 'custom:allowed', 'color': '#22c55e', 'source': 'custom'},
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 201


def test_api_create_duplicate_name(client):
    client.post('/api/tags/',
        json={'name': 'custom:dup'},
        headers={'X-API-KEY': 'admin_api_key'})
    res = client.post('/api/tags/',
        json={'name': 'custom:dup'},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


def test_api_create_missing_name(client):
    res = client.post('/api/tags/',
        json={'color': '#000'},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


# ── API PUT update ────────────────────────────────────────────────────────────

def test_api_update_admin_ok(client, app):
    uuid = _create_tag(app, name='update:test')
    res = client.put(f'/api/tags/{uuid}',
        json={'description': 'Updated description'},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    assert res.get_json()['description'] == 'Updated description'


def test_api_update_not_found(client):
    res = client.put('/api/tags/00000000-0000-0000-0000-000000000000',
        json={'description': 'x'},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 404


def test_api_update_no_perm(client, app):
    uuid = _create_tag(app, name='update:no-perm')
    res = client.put(f'/api/tags/{uuid}',
        json={'description': 'x'},
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


# ── API DELETE ────────────────────────────────────────────────────────────────

def test_api_delete_admin_ok(client, app):
    uuid = _create_tag(app, name='delete:test')
    res = client.delete(f'/api/tags/{uuid}',
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200


def test_api_delete_no_perm(client, app):
    uuid = _create_tag(app, name='delete:noperm')
    res = client.delete(f'/api/tags/{uuid}',
        headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_delete_reader_blocked(client, app):
    uuid = _create_tag(app, name='delete:reader')
    res = client.delete(f'/api/tags/{uuid}',
        headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


# ── API bulk ──────────────────────────────────────────────────────────────────

def test_api_bulk_admin_ok(client, app):
    uuid = _create_tag(app, name='bulk:test')
    res = client.post('/api/tags/bulk',
        json={'action': 'deactivate', 'uuids': [uuid]},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    assert res.get_json()['count'] == 1


def test_api_bulk_invalid_action(client):
    res = client.post('/api/tags/bulk',
        json={'action': 'explode', 'uuids': []},
        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


def test_api_bulk_no_perm(client, app):
    uuid = _create_tag(app, name='bulk:noperm')
    res = client.post('/api/tags/bulk',
        json={'action': 'delete', 'uuids': [uuid]},
        headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


# ── Visibility — private custom tag ──────────────────────────────────────────

def test_private_tag_not_visible_to_others(client, app):
    """A private custom tag should not appear in the list for users who didn't create it."""
    _grant_permission(app, 'Editor', 'tags.view')
    # Admin creates a private tag
    _create_tag(app, name='private:secret', is_public=False, source='custom')
    # Editor should not see it
    res = client.get('/api/tags/', headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 200
    names = [t['name'] for t in res.get_json()['items']]
    assert 'private:secret' not in names


def test_public_tag_visible_to_all(client, app):
    """A public taxonomy tag should appear for all users with tags.view."""
    _grant_permission(app, 'Editor', 'tags.view')
    _create_tag(app, name='tlp:green', is_public=True, source='taxonomy')
    res = client.get('/api/tags/', headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 200
    names = [t['name'] for t in res.get_json()['items']]
    assert 'tlp:green' in names


# ── Namespaces endpoint ───────────────────────────────────────────────────────

def test_api_namespaces_admin(client, app):
    _create_tag(app, name='alpha:one', source='taxonomy', is_public=True)
    res = client.get('/api/tags/namespaces', headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    assert 'alpha' in res.get_json()['namespaces']
