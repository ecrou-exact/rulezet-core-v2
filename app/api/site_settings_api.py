import re
from pathlib import Path

from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission
from ..core.utils.logger import log_action, api_category
from ..features.site_settings.site_settings_core import (
    get_system_info,
    get_smtp_config,
    save_smtp_config_core,
    regenerate_session_key_core,
    get_server_config,
    save_server_config_core,
    restart_server,
    list_submodules,
    validate_new_submodule,
)

site_settings_ns = Namespace('site-settings', description='Server & environment configuration')


@site_settings_ns.route('/server')
class ServerConfig(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        return get_server_config(), 200

    def post(self):
        data = request.get_json(silent=True) or {}
        host = data.get('host', '').strip()
        port = data.get('port')
        if not host:
            return {'message': 'Host is required'}, 400
        try:
            port = int(port)
        except (TypeError, ValueError):
            return {'message': 'Port must be a number'}, 400

        ok, msg = save_server_config_core(host, port)
        if not ok:
            return {'message': msg}, 400

        log_action(
            f"Server binding changed to {host}:{port}",
            "edit",
            category=api_category('admin'),
            level="warning",
            object_type="server_config",
            is_public=False,
            meta={'host': host, 'port': port},
        )
        restart_server()
        return {'message': msg, 'host': host, 'port': port}, 200


@site_settings_ns.route('/system')
class SystemInfo(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        return get_system_info(), 200


@site_settings_ns.route('/smtp')
class SmtpConfig(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        return get_smtp_config(), 200

    def post(self):
        data = request.get_json(silent=True) or {}
        ok, msg = save_smtp_config_core(data)
        if ok:
            log_action(
                "SMTP config updated",
                "smtp_config_update",
                category=api_category('admin'),
                level="info",
                object_type="smtp_config",
                is_public=False,
                meta={
                    'smtp_host': data.get('smtp_host', ''),
                    'smtp_port': data.get('smtp_port', ''),
                    'smtp_user': data.get('smtp_user', ''),
                },
            )
        return {'message': msg}, 200 if ok else 400


@site_settings_ns.route('/smtp/test')
class SmtpTest(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        import os
        data = request.get_json(silent=True) or {}
        to   = data.get('to', '').strip()
        if not to:
            uid = current_user.id if current_user.is_authenticated else None
            if uid:
                from ..core.db_class.user import User
                u  = User.query.get(uid)
                to = u.email if u else ''
        if not to:
            return {'message': 'No recipient email provided', 'steps': []}, 400

        host    = os.environ.get('SMTP_HOST', '').strip()
        port    = os.environ.get('SMTP_PORT', '587').strip()
        user    = os.environ.get('SMTP_USER', '').strip()
        sender  = os.environ.get('SMTP_SENDER', '').strip() or user
        use_tls = os.environ.get('SMTP_USE_TLS', '1').strip() == '1'

        steps = [
            f"Recipient   : {to}",
            f"SMTP host   : {host or '(not set)'}",
            f"SMTP port   : {port}",
            f"SMTP user   : {user or '(not set)'}",
            f"Sender      : {sender or '(not set)'}",
            f"Encryption  : {'STARTTLS' if use_tls else 'SSL/TLS'}",
        ]

        from ..core.utils.mailer import send_test_email
        ok, msg = send_test_email(to)

        steps.append(f"Result      : {'✓ ' if ok else '✗ '}{msg}")

        log_action(
            f"SMTP test {'succeeded' if ok else 'failed'}: {msg}",
            "smtp_test",
            category=api_category('admin'),
            level="success" if ok else "warning",
            object_type="smtp_config",
            is_public=False,
            meta={'to': to, 'host': host, 'port': port, 'ok': ok, 'error': msg if not ok else None},
        )

        return {'message': msg, 'steps': steps, 'ok': ok}, 200 if ok else 400


@site_settings_ns.route('/session-key')
class SessionKey(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        _, msg = regenerate_session_key_core()
        log_action(
            "Session key regenerated",
            "session_key_regenerate",
            category=api_category('admin'),
            level="warning",
            object_type="site_settings",
            is_public=False,
        )
        return {'message': msg}, 200


@site_settings_ns.route('/packages')
class PackageList(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        """Return all installed Python packages, with optional ?q= search filter."""
        from ..features.site_settings.site_settings_core import get_installed_packages
        pkgs = get_installed_packages()
        q = request.args.get('q', '').strip().lower()
        if q:
            pkgs = [p for p in pkgs if q in p['name'].lower()]
        return {'items': pkgs, 'total': len(pkgs)}, 200


@site_settings_ns.route('/packages/update')
class PackageUpdate(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        """Upgrade an installed package via pip."""
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        if not name:
            return {'message': 'Package name required'}, 400
        from ..features.site_settings.site_settings_core import update_package_core
        ok, output = update_package_core(name)
        if ok:
            log_action(
                f"Package updated: {name}",
                "package_update",
                category=api_category('admin'),
                level="success",
                object_type="package",
                is_public=False,
                meta={'name': name},
            )
        return {'message': output, 'ok': ok}, 200 if ok else 400


@site_settings_ns.route('/packages/install')
class PackageInstall(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        """Install a new package via pip."""
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        if not name:
            return {'message': 'Package name required'}, 400
        from ..features.site_settings.site_settings_core import install_package_core
        ok, output = install_package_core(name)
        if ok:
            log_action(
                f"Package installed: {name}",
                "package_install",
                category=api_category('admin'),
                level="success",
                object_type="package",
                is_public=False,
                meta={'name': name},
            )
        return {'message': output, 'ok': ok}, 200 if ok else 400


# ── Submodules ─────────────────────────────────────────────────────────────────

@site_settings_ns.route('/submodules')
class SubmoduleList(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        """List all git submodules with their current status."""
        return {'submodules': list_submodules()}, 200

    def post(self):
        """
        Add a new git submodule via a background job.

        Body:
        - url    (str, required): Git clone URL (https:// or git@)
        - path   (str, required): Local relative path (e.g. "modules/my-lib")
        - branch (str, optional): Branch to track
        """
        data   = request.get_json(silent=True) or {}
        url    = data.get('url',    '').strip()
        path   = data.get('path',   '').strip()
        branch = data.get('branch', '').strip()

        ok, msg = validate_new_submodule(url, path, branch)
        if not ok:
            return {'message': msg}, 400

        from ..core.utils.job_runner import enqueue_job
        uid = current_user.id if current_user.is_authenticated else None
        job = enqueue_job(
            'site_settings.submodule_add',
            title=f"Add submodule: {path}",
            meta={'url': url, 'path': path, 'branch': branch},
            user_id=uid,
        )
        log_action(
            f"Submodule add queued: {path} ({url})",
            "create",
            category=api_category('admin'),
            level="info",
            object_type="submodule",
            is_public=False,
            meta={'url': url, 'path': path, 'branch': branch, 'job_id': job.id},
        )
        return {'message': 'Submodule add job queued', 'job': job.to_json()}, 202


@site_settings_ns.route('/submodules/update')
class SubmoduleUpdate(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        """
        Update one or all submodules via a background job.

        Body:
        - path (str, optional): Submodule path to update. Omit or null for all.
        """
        data = request.get_json(silent=True) or {}
        path = (data.get('path') or '').strip() or None

        from ..core.utils.job_runner import enqueue_job
        uid   = current_user.id if current_user.is_authenticated else None
        title = f"Update submodule: {path}" if path else "Update all submodules"
        job   = enqueue_job(
            'site_settings.submodule_update',
            title=title,
            meta={'path': path},
            user_id=uid,
        )
        log_action(
            f"Submodule update queued: {path or 'all'}",
            "edit",
            category=api_category('admin'),
            level="info",
            object_type="submodule",
            is_public=False,
            meta={'path': path, 'job_id': job.id},
        )
        return {'message': title + ' — job queued', 'job': job.to_json()}, 202


@site_settings_ns.route('/submodules/tree')
class SubmoduleTree(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def get(self):
        """Return the file tree of a submodule directory (max 3 levels deep)."""
        path_str = (request.args.get('path') or '').strip()
        if not re.match(r'^modules/[\w\-\.]+$', path_str):
            return {'message': 'Invalid path — must be modules/<name>'}, 400

        root = Path(path_str)
        if not root.exists() or not root.is_dir():
            return {'message': 'Directory not found', 'tree': []}, 404

        def build(p, depth=0):
            nodes = []
            try:
                entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
                for entry in entries[:300]:
                    node = {
                        'name': entry.name,
                        'path': str(entry),
                        'type': 'dir' if entry.is_dir() else 'file',
                        'ext':  entry.suffix.lstrip('.').lower() if entry.is_file() else None,
                    }
                    if entry.is_dir() and depth < 3:
                        node['children'] = build(entry, depth + 1)
                    elif entry.is_dir():
                        node['children'] = []
                    nodes.append(node)
            except PermissionError:
                pass
            return nodes

        return {'tree': build(root)}, 200


@site_settings_ns.route('/submodules/file')
class SubmoduleFile(Resource):
    method_decorators = [api_require_permission('admin_only')]

    MAX_BYTES = 512 * 1024  # 512 KB

    def get(self):
        """Return text content of a file inside a submodule (read-only)."""
        path_str = (request.args.get('path') or '').strip()
        if not re.match(r'^modules/[\w\-\./]+$', path_str):
            return {'message': 'Invalid path'}, 400

        # Resolve and ensure path stays inside the project
        project_root = Path('.').resolve()
        target = (project_root / path_str).resolve()
        if not str(target).startswith(str(project_root / 'modules')):
            return {'message': 'Path traversal not allowed'}, 403

        if not target.exists():
            return {'message': 'File not found'}, 404
        if not target.is_file():
            return {'message': 'Path is not a file'}, 400
        if target.stat().st_size > self.MAX_BYTES:
            return {'message': f'File too large (>{self.MAX_BYTES // 1024} KB)'}, 400

        try:
            content = target.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return {'message': f'Could not read file: {e}'}, 500

        return {'content': content, 'path': path_str, 'name': target.name}, 200


@site_settings_ns.route('/submodules/remove')
class SubmoduleRemove(Resource):
    method_decorators = [api_require_permission('admin_only')]

    def post(self):
        """
        Remove a git submodule via a background job.

        Body:
        - path (str, required): Submodule relative path (e.g. "modules/my-lib")
        - name (str, optional): Submodule name (defaults to basename of path)
        """
        data = request.get_json(silent=True) or {}
        path = (data.get('path') or '').strip()
        if not path:
            return {'message': 'Submodule path is required'}, 400

        from ..features.site_settings.site_settings_core import _validate_submodule_path
        if not _validate_submodule_path(path):
            return {'message': 'Invalid submodule path'}, 400

        # Confirm submodule actually exists before queuing
        existing = list_submodules()
        match = next((s for s in existing if s['path'] == path), None)
        if not match:
            return {'message': f"No submodule found at '{path}'"}, 404

        name = match.get('name') or path.split('/')[-1]
        from ..core.utils.job_runner import enqueue_job
        uid = current_user.id if current_user.is_authenticated else None
        job = enqueue_job(
            'site_settings.submodule_remove',
            title=f"Remove submodule: {name}",
            meta={'path': path, 'name': name},
            user_id=uid,
        )
        log_action(
            f"Submodule remove queued: {path}",
            "delete",
            category=api_category('admin'),
            level="warning",
            object_type="submodule",
            is_public=False,
            meta={'path': path, 'name': name, 'job_id': job.id},
        )
        return {'message': f"Remove '{name}' — job queued", 'job': job.to_json()}, 202
