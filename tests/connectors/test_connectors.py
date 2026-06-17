"""Tests for the Connectors feature."""
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth(api_key):
    return {'X-API-KEY': api_key}


def _create(client, payload=None):
    payload = payload or {
        'name':         'Test Connector',
        'url':          'https://remote.example.com',
        'outgoing_key': 'remote-api-key',
        'direction':    'pull',
        'sync_tags':    True,
    }
    return client.post('/api/connectors/', json=payload, headers=_auth('admin_api_key'))


# ── HTML route ────────────────────────────────────────────────────────────────

class TestConnectorPage:
    def test_admin_can_view(self, client):
        r = client.get('/connectors/', headers={'X-API-KEY': 'admin_api_key'})
        # HTML route uses session — login instead
        r = client.post('/account/login', data={'email': 'admin@admin.admin', 'password': 'admin'}, follow_redirects=True)
        r = client.get('/connectors/')
        assert r.status_code == 200

    def test_anon_redirected(self, client):
        r = client.get('/connectors/')
        assert r.status_code == 302

    def test_read_only_forbidden(self, client):
        client.post('/account/login', data={'email': 'read@read.read', 'password': 'read'}, follow_redirects=True)
        r = client.get('/connectors/')
        assert r.status_code == 403


# ── API list ──────────────────────────────────────────────────────────────────

class TestConnectorList:
    def test_admin_list_empty(self, client):
        r = client.get('/api/connectors/', headers=_auth('admin_api_key'))
        assert r.status_code == 200
        data = r.get_json()
        assert data['total'] == 0

    def test_editor_forbidden(self, client):
        r = client.get('/api/connectors/', headers=_auth('editor_api_key'))
        assert r.status_code == 403

    def test_read_forbidden(self, client):
        r = client.get('/api/connectors/', headers=_auth('read_api_key'))
        assert r.status_code == 403


# ── API create ────────────────────────────────────────────────────────────────

class TestConnectorCreate:
    def test_admin_create(self, client):
        r = _create(client)
        assert r.status_code == 201
        data = r.get_json()
        assert data['name'] == 'Test Connector'
        assert data['direction'] == 'pull'
        assert data['status'] == 'unknown'
        assert 'incoming_key' in data

    def test_create_missing_name(self, client):
        r = client.post('/api/connectors/', json={'url': 'https://x.com', 'direction': 'pull'}, headers=_auth('admin_api_key'))
        assert r.status_code == 400

    def test_create_missing_url(self, client):
        r = client.post('/api/connectors/', json={'name': 'X', 'direction': 'pull'}, headers=_auth('admin_api_key'))
        assert r.status_code == 400

    def test_create_invalid_direction(self, client):
        r = client.post('/api/connectors/', json={'name': 'X', 'url': 'https://x.com', 'direction': 'invalid'}, headers=_auth('admin_api_key'))
        assert r.status_code == 400

    def test_editor_forbidden(self, client):
        r = client.post('/api/connectors/', json={'name': 'X', 'url': 'https://x.com', 'direction': 'pull'}, headers=_auth('editor_api_key'))
        assert r.status_code == 403


# ── API read / update / delete ────────────────────────────────────────────────

class TestConnectorCRUD:
    def test_get_one(self, client):
        created = _create(client).get_json()
        r = client.get(f'/api/connectors/{created["uuid"]}', headers=_auth('admin_api_key'))
        assert r.status_code == 200
        assert r.get_json()['uuid'] == created['uuid']

    def test_get_not_found(self, client):
        r = client.get('/api/connectors/nonexistent-uuid', headers=_auth('admin_api_key'))
        assert r.status_code == 404

    def test_update(self, client):
        created = _create(client).get_json()
        r = client.put(f'/api/connectors/{created["uuid"]}',
                       json={'name': 'Updated Name', 'direction': 'push'},
                       headers=_auth('admin_api_key'))
        assert r.status_code == 200
        assert r.get_json()['name'] == 'Updated Name'
        assert r.get_json()['direction'] == 'push'

    def test_delete(self, client):
        created = _create(client).get_json()
        r = client.delete(f'/api/connectors/{created["uuid"]}', headers=_auth('admin_api_key'))
        assert r.status_code == 200
        r2 = client.get(f'/api/connectors/{created["uuid"]}', headers=_auth('admin_api_key'))
        assert r2.status_code == 404

    def test_delete_not_found(self, client):
        r = client.delete('/api/connectors/nonexistent', headers=_auth('admin_api_key'))
        assert r.status_code == 404


# ── Test / Sync job enqueue ───────────────────────────────────────────────────

class TestConnectorJobs:
    def test_test_no_key(self, client):
        r = client.post('/api/connectors/', json={'name': 'X', 'url': 'https://x.com', 'direction': 'pull'}, headers=_auth('admin_api_key'))
        uuid = r.get_json()['uuid']
        r2 = client.post(f'/api/connectors/{uuid}/test', headers=_auth('admin_api_key'))
        assert r2.status_code == 400  # no outgoing_key configured

    def test_sync_push_only(self, client):
        r = client.post('/api/connectors/', json={'name': 'X', 'url': 'https://x.com', 'direction': 'push', 'outgoing_key': 'k'}, headers=_auth('admin_api_key'))
        uuid = r.get_json()['uuid']
        r2 = client.post(f'/api/connectors/{uuid}/sync', headers=_auth('admin_api_key'))
        assert r2.status_code == 400  # push-only

    def test_editor_cannot_test(self, client):
        created = _create(client).get_json()
        r = client.post(f'/api/connectors/{created["uuid"]}/test', headers=_auth('editor_api_key'))
        assert r.status_code == 403


# ── Incoming push ─────────────────────────────────────────────────────────────

class TestConnectorIncoming:
    def test_valid_push(self, client):
        # Create a push connector
        r = client.post('/api/connectors/', json={
            'name': 'Remote', 'url': 'https://remote.com',
            'direction': 'push', 'sync_tags': True,
        }, headers=_auth('admin_api_key'))
        incoming_key = r.get_json()['incoming_key']

        tags = [{'name': 'tlp:red', 'color': '#ff0000', 'source': 'taxonomy', 'namespace': 'tlp'}]
        r2 = client.post(f'/api/connectors/push/{incoming_key}', json={'tags': tags, 'source_name': 'Remote'})
        assert r2.status_code == 200
        assert r2.get_json()['count'] == 1

    def test_invalid_key(self, client):
        r = client.post('/api/connectors/push/invalid-key-xyz', json={'tags': []})
        assert r.status_code == 404

    def test_pull_only_rejects_push(self, client):
        r = client.post('/api/connectors/', json={
            'name': 'Remote', 'url': 'https://remote.com',
            'direction': 'pull', 'outgoing_key': 'key',
        }, headers=_auth('admin_api_key'))
        incoming_key = r.get_json()['incoming_key']
        r2 = client.post(f'/api/connectors/push/{incoming_key}', json={'tags': []})
        assert r2.status_code == 404
