"""Tests for Template Studio and Dynamic Pages.

Covers:
- HTML routes: index, new, edit, preview — admin only
- POST actions: save (create + update), publish, unpublish, delete
- Dynamic page route: /pages/<slug>
- Role boundaries: anonymous (redirect), editor/read-only (403), admin (OK)
- Slug uniqueness, slug auto-generation
- Publish/unpublish flow
"""
import pytest
from app import db
from app.core.db_class.page_definition import PageDefinition


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_page(app, name='Test Page', slug='test-page', published=False, nav_group=None):
    with app.app_context():
        page = PageDefinition(
            name=name,
            slug=slug,
            nav_group=nav_group,
            nav_label=name,
            nav_icon='fa-file',
            required_permission=None,
            sections=[],
            is_published=published,
            created_by=1,
        )
        db.session.add(page)
        db.session.commit()
        return page.uuid


def _login(client, email, password):
    client.post('/account/login', data={'email': email, 'password': password}, follow_redirects=True)


def _login_admin(client):
    _login(client, 'admin@admin.admin', 'admin')


def _login_editor(client):
    _login(client, 'editor@editor.editor', 'editor')


def _login_reader(client):
    _login(client, 'read@read.read', 'read')


# ── Index page ────────────────────────────────────────────────────────────────

class TestIndexHTML:

    def test_anonymous_redirects(self, client):
        r = client.get('/admin/template-studio/')
        assert r.status_code == 302
        assert '/account/login' in r.headers['Location']

    def test_editor_forbidden(self, client):
        _login_editor(client)
        r = client.get('/admin/template-studio/')
        assert r.status_code == 403

    def test_reader_forbidden(self, client):
        _login_reader(client)
        r = client.get('/admin/template-studio/')
        assert r.status_code == 403

    def test_admin_ok(self, client):
        _login_admin(client)
        r = client.get('/admin/template-studio/')
        assert r.status_code == 200
        assert b'Template Studio' in r.data

    def test_lists_pages(self, client, app):
        uuid = _make_page(app, 'My Awesome Page', 'my-awesome-page')
        _login_admin(client)
        r = client.get('/admin/template-studio/')
        assert b'My Awesome Page' in r.data


# ── New page (builder) ────────────────────────────────────────────────────────

class TestBuilderHTML:

    def test_new_anonymous_redirects(self, client):
        r = client.get('/admin/template-studio/new')
        assert r.status_code == 302

    def test_new_admin_ok(self, client):
        _login_admin(client)
        r = client.get('/admin/template-studio/new')
        assert r.status_code == 200

    def test_edit_admin_ok(self, client, app):
        uuid = _make_page(app)
        _login_admin(client)
        r = client.get(f'/admin/template-studio/{uuid}')
        assert r.status_code == 200

    def test_edit_not_found(self, client):
        _login_admin(client)
        r = client.get('/admin/template-studio/00000000-0000-0000-0000-000000000000')
        assert r.status_code == 404

    def test_preview_admin_ok(self, client, app):
        uuid = _make_page(app)
        _login_admin(client)
        r = client.get(f'/admin/template-studio/{uuid}/preview')
        assert r.status_code == 200

    def test_preview_not_found(self, client):
        _login_admin(client)
        r = client.get('/admin/template-studio/00000000-0000-0000-0000-000000000000/preview')
        assert r.status_code == 404


# ── Save (create) ─────────────────────────────────────────────────────────────

class TestSaveCreate:

    def test_anonymous_forbidden(self, client):
        r = client.post('/admin/template-studio/save', json={'name': 'x', 'slug': 'x'})
        assert r.status_code == 302

    def test_editor_forbidden(self, client):
        _login_editor(client)
        r = client.post('/admin/template-studio/save', json={'name': 'x', 'slug': 'x'})
        assert r.status_code == 403

    def test_create_ok(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'name': 'New Page', 'slug': 'new-page',
            'description': 'A test page',
            'sections': [],
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d['ok'] is True
        assert 'uuid' in d

    def test_create_missing_name(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={'slug': 'test'})
        assert r.status_code == 400
        assert r.get_json()['ok'] is False

    def test_create_no_data(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', data='not-json',
                        content_type='application/json')
        assert r.status_code == 400

    def test_create_duplicate_slug(self, client, app):
        _make_page(app, 'Existing', 'dupe-slug')
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={'name': 'Another', 'slug': 'dupe-slug'})
        assert r.status_code == 400
        assert 'already exists' in r.get_json()['message']

    def test_create_auto_slugify(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={'name': 'My Cool Page'})
        assert r.status_code == 200
        d = r.get_json()
        assert d['ok'] is True

    def test_create_with_sections(self, client):
        _login_admin(client)
        sections = [
            {'id': 'aaa', 'type': 'page_header', 'config': {'title': 'Test', 'breadcrumb': []}},
            {'id': 'bbb', 'type': 'data_table', 'config': {'fetch_url': '/api/items/', 'columns': []}},
        ]
        r = client.post('/admin/template-studio/save', json={
            'name': 'With Sections', 'slug': 'with-sections', 'sections': sections,
        })
        assert r.status_code == 200

    def test_create_stores_nav_info(self, client, app):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'name': 'Nav Page', 'slug': 'nav-page',
            'nav_group': 'Admin', 'nav_label': 'My Nav Page', 'nav_icon': 'fa-star',
        })
        assert r.status_code == 200
        uuid = r.get_json()['uuid']
        with app.app_context():
            page = PageDefinition.query.filter_by(uuid=uuid).first()
            assert page.nav_group == 'Admin'
            assert page.nav_icon == 'fa-star'

    def test_create_stores_permission(self, client, app):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'name': 'Restricted', 'slug': 'restricted',
            'required_permission': 'admin_only',
        })
        assert r.status_code == 200
        uuid = r.get_json()['uuid']
        with app.app_context():
            page = PageDefinition.query.filter_by(uuid=uuid).first()
            assert page.required_permission == 'admin_only'


# ── Save (update) ─────────────────────────────────────────────────────────────

class TestSaveUpdate:

    def test_update_ok(self, client, app):
        uuid = _make_page(app, 'Original', 'original-slug')
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'uuid': uuid, 'name': 'Updated Name', 'slug': 'updated-slug',
        })
        assert r.status_code == 200
        with app.app_context():
            page = PageDefinition.query.filter_by(uuid=uuid).first()
            assert page.name == 'Updated Name'
            assert page.slug == 'updated-slug'

    def test_update_not_found(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'uuid': '00000000-0000-0000-0000-000000000000', 'name': 'x',
        })
        assert r.status_code == 400

    def test_update_slug_conflict(self, client, app):
        _make_page(app, 'Other Page', 'taken-slug')
        uuid = _make_page(app, 'Mine', 'mine-slug')
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'uuid': uuid, 'name': 'Mine', 'slug': 'taken-slug',
        })
        assert r.status_code == 400

    def test_update_same_slug_ok(self, client, app):
        uuid = _make_page(app, 'Page', 'my-slug')
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={
            'uuid': uuid, 'name': 'Page Updated', 'slug': 'my-slug',
        })
        assert r.status_code == 200


# ── Publish / unpublish ───────────────────────────────────────────────────────

class TestPublish:

    def test_publish_ok(self, client, app):
        uuid = _make_page(app, published=False)
        _login_admin(client)
        r = client.post(f'/admin/template-studio/{uuid}/publish')
        assert r.status_code == 200
        with app.app_context():
            assert PageDefinition.query.filter_by(uuid=uuid).first().is_published is True

    def test_publish_not_found(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/00000000-0000-0000-0000-000000000000/publish')
        assert r.status_code == 404

    def test_unpublish_ok(self, client, app):
        uuid = _make_page(app, published=True)
        _login_admin(client)
        r = client.post(f'/admin/template-studio/{uuid}/unpublish')
        assert r.status_code == 200
        with app.app_context():
            assert PageDefinition.query.filter_by(uuid=uuid).first().is_published is False

    def test_publish_editor_forbidden(self, client, app):
        uuid = _make_page(app)
        _login_editor(client)
        r = client.post(f'/admin/template-studio/{uuid}/publish')
        assert r.status_code == 403


# ── Delete ─────────────────────────────────────────────────────────────────────

class TestDelete:

    def test_delete_ok(self, client, app):
        uuid = _make_page(app)
        _login_admin(client)
        r = client.post(f'/admin/template-studio/{uuid}/delete')
        assert r.status_code == 200
        with app.app_context():
            page = PageDefinition.query.filter_by(uuid=uuid).first()
            assert page.is_active is False

    def test_delete_not_found(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/00000000-0000-0000-0000-000000000000/delete')
        assert r.status_code == 404

    def test_delete_editor_forbidden(self, client, app):
        uuid = _make_page(app)
        _login_editor(client)
        r = client.post(f'/admin/template-studio/{uuid}/delete')
        assert r.status_code == 403

    def test_deleted_page_not_in_list(self, client, app):
        uuid = _make_page(app, 'Doomed Page', 'doomed-page')
        _login_admin(client)
        client.post(f'/admin/template-studio/{uuid}/delete')
        r = client.get('/admin/template-studio/')
        assert b'Doomed Page' not in r.data


# ── Dynamic pages (/pages/<slug>) ─────────────────────────────────────────────

class TestDynamicPages:

    def test_anonymous_redirects(self, client, app):
        _make_page(app, 'Public Page', 'public-page', published=True)
        r = client.get('/pages/public-page')
        assert r.status_code == 302
        assert '/account/login' in r.headers['Location']

    def test_not_found_unpublished(self, client, app):
        _make_page(app, 'Draft Page', 'draft-page', published=False)
        _login_admin(client)
        r = client.get('/pages/draft-page')
        assert r.status_code == 404

    def test_not_found_unknown_slug(self, client):
        _login_admin(client)
        r = client.get('/pages/does-not-exist')
        assert r.status_code == 404

    def test_published_admin_ok(self, client, app):
        _make_page(app, 'Live Page', 'live-page', published=True)
        _login_admin(client)
        r = client.get('/pages/live-page')
        assert r.status_code == 200

    def test_published_editor_ok_no_perm_req(self, client, app):
        _make_page(app, 'Open Page', 'open-page', published=True)
        _login_editor(client)
        r = client.get('/pages/open-page')
        assert r.status_code == 200

    def test_admin_only_page_blocks_editor(self, client, app):
        with app.app_context():
            page = PageDefinition(
                name='Admin Page', slug='admin-only-page',
                required_permission='admin_only',
                is_published=True, sections=[], created_by=1,
            )
            db.session.add(page)
            db.session.commit()
        _login_editor(client)
        r = client.get('/pages/admin-only-page')
        assert r.status_code == 403

    def test_admin_only_page_allows_admin(self, client, app):
        with app.app_context():
            page = PageDefinition(
                name='Admin Only', slug='admin-only-2',
                required_permission='admin_only',
                is_published=True, sections=[], created_by=1,
            )
            db.session.add(page)
            db.session.commit()
        _login_admin(client)
        r = client.get('/pages/admin-only-2')
        assert r.status_code == 200

    def test_reader_can_access_open_page(self, client, app):
        _make_page(app, 'Reader Page', 'reader-page', published=True)
        _login_reader(client)
        r = client.get('/pages/reader-page')
        assert r.status_code == 200


# ── Core (slugify) ─────────────────────────────────────────────────────────────

class TestSlugify:

    def test_spaces_to_hyphens(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={'name': 'Hello World'})
        assert r.status_code == 200
        uuid = r.get_json()['uuid']
        from app import db
        with client.application.app_context():
            p = PageDefinition.query.filter_by(uuid=uuid).first()
            assert p.slug == 'hello-world'

    def test_special_chars_stripped(self, client):
        _login_admin(client)
        r = client.post('/admin/template-studio/save', json={'name': 'Hello! @World#123'})
        assert r.status_code == 200
        uuid = r.get_json()['uuid']
        with client.application.app_context():
            p = PageDefinition.query.filter_by(uuid=uuid).first()
            assert p.slug == 'hello-world123'
