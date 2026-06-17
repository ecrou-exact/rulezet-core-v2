"""
test_comments.py — Tests for the Comment system.

Roles:
  admin   → admin@admin.admin   / admin_api_key  (bypasses all perms)
  editor  → editor@editor.editor / editor_api_key  (no special perms by default)
  reader  → read@read.read      / read_api_key   (read_only role)
"""
import pytest


def login_as(client, email, password):
    return client.post('/account/login',
        data={'email': email, 'password': password},
        follow_redirects=True)


def _grant_permission(app, role_name, perm_key):
    """Helper to grant a permission to a named role."""
    from app.core.db_class.user import Role, RolePermission
    from app import db
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        if role and not role.has_permission(perm_key):
            rp = RolePermission(role_id=role.id, permission=perm_key)
            db.session.add(rp)
            db.session.commit()


# ── Forum HTML route ──────────────────────────────────────────────────────────

def test_forum_public_access(client):
    """Anonymous user can access the forum (public page)."""
    res = client.get('/comments/', follow_redirects=False)
    assert res.status_code == 200


def test_forum_admin_can_access(client, app):
    """Admin bypasses all permission checks."""
    login_as(client, 'admin@admin.admin', 'admin')
    res = client.get('/comments/')
    assert res.status_code == 200


def test_forum_no_permission_still_viewable(client):
    """Editor without comments.view can still view the forum (public page)."""
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/comments/')
    assert res.status_code == 200


def test_forum_with_view_permission(client, app):
    """User with comments.view can access the forum."""
    _grant_permission(app, 'Editor', 'comments.view')
    login_as(client, 'editor@editor.editor', 'editor')
    res = client.get('/comments/')
    assert res.status_code == 200


# ── API GET comments ──────────────────────────────────────────────────────────

def test_api_get_comments_admin(client):
    """Admin can list comments for a given object."""
    res = client.get('/api/comments?object_type=forum&object_id=1',
                     headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'items' in data
    assert 'total' in data
    assert isinstance(data['items'], list)


def test_api_get_comments_anon_forbidden(client):
    """Unauthenticated request is forbidden."""
    res = client.get('/api/comments?object_type=forum&object_id=1')
    assert res.status_code == 403


def test_api_get_comments_missing_params(client):
    """Missing object_type or object_id returns 400."""
    res = client.get('/api/comments',
                     headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


# ── API POST comment ──────────────────────────────────────────────────────────

def test_api_create_comment_admin(client):
    """Admin can post a top-level comment."""
    res = client.post('/api/comments',
                      json={'object_type': 'forum', 'object_id': 1, 'content': 'Hello world'},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 201
    data = res.get_json()
    assert 'comment' in data
    assert data['comment']['content'] == 'Hello world'
    assert data['comment']['depth'] == 0


def test_api_create_comment_depth_tracking(client):
    """Reply depth is set correctly."""
    # Create root comment
    r1 = client.post('/api/comments',
                     json={'object_type': 'forum', 'object_id': 1, 'content': 'Root'},
                     headers={'X-API-KEY': 'admin_api_key'})
    assert r1.status_code == 201
    root_id = r1.get_json()['comment']['id']

    # Create reply
    r2 = client.post('/api/comments',
                     json={'object_type': 'forum', 'object_id': 1,
                           'content': 'Reply', 'parent_id': root_id},
                     headers={'X-API-KEY': 'admin_api_key'})
    assert r2.status_code == 201
    reply = r2.get_json()['comment']
    assert reply['depth'] == 1
    assert reply['parent_id'] == root_id


def test_api_create_comment_depth_limit(client):
    """Replies deeper than 4 levels are rejected."""
    # Build 5 levels deep
    parent_id = None
    for i in range(5):
        payload = {'object_type': 'forum', 'object_id': 1, 'content': f'Level {i}'}
        if parent_id is not None:
            payload['parent_id'] = parent_id
        res = client.post('/api/comments', json=payload,
                          headers={'X-API-KEY': 'admin_api_key'})
        if res.status_code != 201:
            # Should have failed at depth 5
            assert i == 4
            assert res.status_code == 400
            return
        parent_id = res.get_json()['comment']['id']

    # 6th level should fail
    res = client.post('/api/comments',
                      json={'object_type': 'forum', 'object_id': 1,
                            'content': 'Too deep', 'parent_id': parent_id},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


def test_api_create_comment_no_permission(client):
    """Editor without comments.create permission is forbidden."""
    res = client.post('/api/comments',
                      json={'object_type': 'forum', 'object_id': 1, 'content': 'Test'},
                      headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


def test_api_create_comment_empty_content(client):
    """Empty content returns 400."""
    res = client.post('/api/comments',
                      json={'object_type': 'forum', 'object_id': 1, 'content': '  '},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


# ── API PUT comment ───────────────────────────────────────────────────────────

def _create_comment(client, content='Test comment', api_key='admin_api_key'):
    res = client.post('/api/comments',
                      json={'object_type': 'forum', 'object_id': 1, 'content': content},
                      headers={'X-API-KEY': api_key})
    assert res.status_code == 201
    return res.get_json()['comment']


def test_api_edit_own_comment(client, app):
    """Admin can edit their own comment."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    res = client.put(f'/api/comments/{uuid}',
                     json={'content': 'Edited content'},
                     headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    assert res.get_json()['comment']['content'] == 'Edited content'


def test_api_edit_other_comment_forbidden(client, app):
    """Editor cannot edit another user's comment."""
    # Give editor comments.create so they can post, then try to edit admin's comment
    _grant_permission(app, 'Editor', 'comments.create')
    comment = _create_comment(client)  # created by admin
    uuid    = comment['uuid']

    res = client.put(f'/api/comments/{uuid}',
                     json={'content': 'Hacked'},
                     headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


# ── API DELETE comment ────────────────────────────────────────────────────────

def test_api_soft_delete_own_comment(client):
    """Deleting replaces content with [deleted]."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    res = client.delete(f'/api/comments/{uuid}',
                        headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200

    # Verify content replaced
    r2 = client.get(f'/api/comments/{uuid}',
                    headers={'X-API-KEY': 'admin_api_key'})
    data = r2.get_json()
    assert data['content'] == '[deleted]'
    assert data['is_deleted'] is True


def test_api_delete_other_comment_forbidden(client, app):
    """Reader cannot delete admin's comment."""
    _grant_permission(app, 'Read Only', 'comments.view')
    comment = _create_comment(client)
    uuid    = comment['uuid']

    res = client.delete(f'/api/comments/{uuid}',
                        headers={'X-API-KEY': 'read_api_key'})
    assert res.status_code == 403


# ── API POST react ────────────────────────────────────────────────────────────

def test_api_like_comment(client):
    """Admin can like a comment."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    res = client.post(f'/api/comments/{uuid}/react',
                      json={'reaction': 'like'},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['like_count'] == 1
    assert data['user_reaction'] == 'like'


def test_api_react_toggle_off(client):
    """Liking twice removes the reaction."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    client.post(f'/api/comments/{uuid}/react',
                json={'reaction': 'like'},
                headers={'X-API-KEY': 'admin_api_key'})

    res = client.post(f'/api/comments/{uuid}/react',
                      json={'reaction': 'like'},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['like_count'] == 0
    assert data['user_reaction'] is None


def test_api_react_switch(client):
    """Switching from like to dislike updates correctly."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    client.post(f'/api/comments/{uuid}/react',
                json={'reaction': 'like'},
                headers={'X-API-KEY': 'admin_api_key'})

    res = client.post(f'/api/comments/{uuid}/react',
                      json={'reaction': 'dislike'},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['like_count'] == 0
    assert data['dislike_count'] == 1
    assert data['user_reaction'] == 'dislike'


def test_api_react_invalid(client):
    """Invalid reaction type returns 400."""
    comment = _create_comment(client)
    res = client.post(f'/api/comments/{comment["uuid"]}/react',
                      json={'reaction': 'love'},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 400


# ── API POST restore ──────────────────────────────────────────────────────────

def test_api_restore_admin_can_restore(client):
    """Admin can restore a deleted comment."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    # Delete first
    client.delete(f'/api/comments/{uuid}',
                  headers={'X-API-KEY': 'admin_api_key'})

    # Restore
    res = client.post(f'/api/comments/{uuid}/restore',
                      json={},
                      headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['comment']['is_deleted'] is False


def test_api_restore_editor_forbidden(client, app):
    """Editor without moderate permission cannot restore."""
    comment = _create_comment(client)
    uuid    = comment['uuid']

    # Delete first
    client.delete(f'/api/comments/{uuid}',
                  headers={'X-API-KEY': 'admin_api_key'})

    # Editor tries to restore
    res = client.post(f'/api/comments/{uuid}/restore',
                      json={},
                      headers={'X-API-KEY': 'editor_api_key'})
    assert res.status_code == 403


# ── API GET stats ─────────────────────────────────────────────────────────────

def test_api_stats_returns_list(client):
    """Stats endpoint returns a list of month/count objects."""
    res = client.get('/api/comments/stats/user/1',
                     headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 12  # default 12 months
    for item in data:
        assert 'month' in item
        assert 'count' in item


def test_api_stats_after_comment(client):
    """Stats reflect newly posted comments."""
    # Post a comment as admin
    _create_comment(client, content='Stats test comment')

    # Get stats for admin (user id=1)
    res = client.get('/api/comments/stats/user/1',
                     headers={'X-API-KEY': 'admin_api_key'})
    assert res.status_code == 200
    data   = res.get_json()
    total  = sum(d['count'] for d in data)
    assert total >= 1


def test_api_stats_anon_forbidden(client):
    """Unauthenticated request is forbidden."""
    res = client.get('/api/comments/stats/user/1')
    assert res.status_code == 403
