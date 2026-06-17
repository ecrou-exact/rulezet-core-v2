"""
site_settings_core.py — Read/write .env, expose system info, manage git submodules.

All functions return (value, message) or a plain dict.
No Flask imports except current_app (used inside request context only).
"""
import os
import re
import sys
import secrets
import platform
import subprocess


def _env_path() -> str:
    from flask import current_app
    return os.path.normpath(os.path.join(current_app.root_path, '..', '.env'))


# ── .env read/write ───────────────────────────────────────────────────────────

def _read_env_file() -> dict:
    path = _env_path()
    result: dict = {}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                result[k.strip()] = v.strip()
    return result


def _write_env_file(updates: dict) -> None:
    path  = _env_path()
    env   = _read_env_file()
    env.update({k.upper(): str(v) for k, v in updates.items()})
    with open(path, 'w') as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")


# ── Server binding ────────────────────────────────────────────────────────────

def get_server_config() -> dict:
    return {
        'host': os.environ.get('FLASK_HOST', '127.0.0.1'),
        'port': int(os.environ.get('FLASK_PORT', 7009)),
    }


def save_server_config_core(host: str, port: int) -> tuple[bool, str]:
    import ipaddress
    host = host.strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host not in ('localhost',):
            return False, "Invalid host. Use an IP address (e.g. 127.0.0.1, 0.0.0.0) or 'localhost'."
    if not (1 <= port <= 65535):
        return False, "Port must be between 1 and 65535."
    if port < 1024:
        return False, "Ports below 1024 are reserved — use 1024 or higher."

    _write_env_file({'FLASK_HOST': host, 'FLASK_PORT': str(port)})
    # Update live env so os.execv inherits the new values
    os.environ['FLASK_HOST'] = host
    os.environ['FLASK_PORT'] = str(port)
    return True, "Server config saved."


def restart_server() -> None:
    """Replace the current process image with a fresh start (picks up new env)."""
    import sys
    import threading
    import time

    def _do():
        time.sleep(0.8)
        # os.execv replaces the process image but keeps the PID.
        # Works whether or not Werkzeug's reloader is active.
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do, daemon=True).start()


# ── SMTP ──────────────────────────────────────────────────────────────────────

def get_smtp_config() -> dict:
    return {
        'smtp_host':       os.environ.get('SMTP_HOST', ''),
        'smtp_port':       os.environ.get('SMTP_PORT', '587'),
        'smtp_user':       os.environ.get('SMTP_USER', ''),
        'smtp_sender':     os.environ.get('SMTP_SENDER', ''),
        'smtp_use_tls':    os.environ.get('SMTP_USE_TLS', '1') == '1',
        'smtp_configured': bool(
            os.environ.get('SMTP_HOST', '').strip()
            and os.environ.get('SMTP_USER', '').strip()
        ),
    }


def save_smtp_config_core(data: dict) -> tuple:
    _FIELDS = {
        'smtp_host':     'SMTP_HOST',
        'smtp_port':     'SMTP_PORT',
        'smtp_user':     'SMTP_USER',
        'smtp_password': 'SMTP_PASSWORD',
        'smtp_sender':   'SMTP_SENDER',
        'smtp_use_tls':  'SMTP_USE_TLS',
    }
    updates = {}
    for field, env_key in _FIELDS.items():
        if field in data and data[field] is not None:
            val = str(data[field])
            updates[env_key] = val
            os.environ[env_key] = val  # live effect — no restart needed for SMTP

    _write_env_file(updates)
    return True, "SMTP configuration saved"


# ── Session key ───────────────────────────────────────────────────────────────

def regenerate_session_key_core() -> tuple:
    key = secrets.token_hex(32)
    _write_env_file({'SECRET_KEY': key})
    # os.environ update so the preview reflects the new key immediately
    os.environ['SECRET_KEY'] = key
    return key, "Session key regenerated — restart required to apply"


# ── Package management ───────────────────────────────────────────────────────

def get_installed_packages() -> list:
    """Return all installed packages sorted by name (case-insensitive)."""
    try:
        import importlib.metadata as meta
        dists = sorted(meta.distributions(), key=lambda d: (d.metadata.get('Name') or '').lower())
        result = []
        for d in dists:
            name    = d.metadata.get('Name') or ''
            version = d.metadata.get('Version') or ''
            if name:
                result.append({'name': name, 'version': version})
        return result
    except Exception:
        return []


def _validate_package_name(name: str) -> bool:
    """Only allow safe package names: letters, digits, hyphens, underscores, dots."""
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,99}$', name.strip()))


def update_package_core(name: str) -> tuple:
    """Run pip install --upgrade <name>. Returns (ok, output)."""
    import subprocess
    if not _validate_package_name(name):
        return False, "Invalid package name"
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', name],
            capture_output=True, text=True, timeout=120,
        )
        ok     = result.returncode == 0
        output = (result.stdout.strip() or result.stderr.strip())
        output = output[-500:] if len(output) > 500 else output
        return ok, output
    except Exception as e:
        return False, str(e)


def install_package_core(name: str) -> tuple:
    """Run pip install <name>. Returns (ok, output)."""
    import subprocess
    if not _validate_package_name(name):
        return False, "Invalid package name"
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', name],
            capture_output=True, text=True, timeout=120,
        )
        ok     = result.returncode == 0
        output = (result.stdout.strip() or result.stderr.strip())
        output = output[-500:] if len(output) > 500 else output
        return ok, output
    except Exception as e:
        return False, str(e)


# ── Git submodules ────────────────────────────────────────────────────────────

def _project_root() -> str:
    from flask import current_app
    return os.path.normpath(os.path.join(current_app.root_path, '..'))


def _validate_git_url(url: str) -> bool:
    return bool(
        re.match(r'^https?://[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=%-]+$', url)
        or re.match(r'^git@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+\.git$', url)
    )


def _validate_submodule_path(path: str) -> bool:
    return (
        bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_/.-]*$', path))
        and '..' not in path
        and not os.path.isabs(path)
    )


def _validate_branch_name(branch: str) -> bool:
    return not branch or bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$', branch))


def list_submodules() -> list:
    """Return all submodules with current status from git."""
    root = _project_root()
    gitmodules_path = os.path.join(root, '.gitmodules')

    modules = {}
    if os.path.exists(gitmodules_path):
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(gitmodules_path)
        for section in cfg.sections():
            if section.startswith('submodule '):
                name   = section[len('submodule '):].strip('"')
                m_path = cfg.get(section, 'path', fallback='')
                modules[m_path] = {
                    'name':   name,
                    'path':   m_path,
                    'url':    cfg.get(section, 'url',    fallback=''),
                    'branch': cfg.get(section, 'branch', fallback=''),
                    'commit': '',
                    'status': 'unknown',
                }

    try:
        result = subprocess.run(
            ['git', 'submodule', 'status'],
            capture_output=True, text=True, timeout=10, cwd=root,
        )
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            prefix = line[0]
            parts  = line[1:].split()
            if len(parts) < 2:
                continue
            commit, path = parts[0][:7], parts[1]
            if path in modules:
                modules[path]['commit'] = commit
                modules[path]['status'] = {
                    '-': 'uninitialized',
                    '+': 'out-of-date',
                    ' ': 'up-to-date',
                    'U': 'conflict',
                }.get(prefix, 'unknown')
    except Exception:
        pass

    return list(modules.values())


def validate_new_submodule(url: str, path: str, branch: str) -> tuple[bool, str]:
    if not url or not _validate_git_url(url):
        return False, "Invalid Git URL. Use https:// or git@ format."
    if not path or not _validate_submodule_path(path):
        return False, "Invalid path. Use a safe relative path (e.g. modules/my-lib)."
    if not _validate_branch_name(branch):
        return False, "Invalid branch name."
    # Check for existing submodule with same path or URL
    root = _project_root()
    if os.path.exists(os.path.join(root, path)):
        return False, f"Path '{path}' already exists in the project."
    existing = list_submodules()
    for sub in existing:
        if sub['path'] == path:
            return False, f"A submodule is already registered at '{path}'."
        clean_url = url.rstrip('/').removesuffix('.git')
        clean_existing = sub['url'].rstrip('/').removesuffix('.git')
        if clean_url == clean_existing:
            return False, f"This repository is already added as '{sub['name']}' at '{sub['path']}'."
    return True, "OK"


# ── Submodule job handlers ────────────────────────────────────────────────────

from ...core.utils.job_runner import register_handler


@register_handler('site_settings.submodule_update')
def _submodule_update_handler(ctx, meta):
    from flask import current_app
    root = os.path.normpath(os.path.join(current_app.root_path, '..'))
    path = meta.get('path')

    cmd = ['git', 'submodule', 'update', '--remote', '--merge']
    if path:
        cmd.append(path)
        ctx.log(f"Updating submodule: {path}")
    else:
        ctx.log("Updating all submodules")

    ctx.update_progress(10)
    ctx.checkpoint()

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=root)

    for line in (result.stdout + '\n' + result.stderr).splitlines():
        if line.strip():
            ctx.log(line, level='info' if result.returncode == 0 else 'warning')

    ctx.update_progress(100)

    if result.returncode != 0:
        raise Exception(f"git submodule update failed (exit {result.returncode})")

    ctx.log("Update complete.", level='success')
    return {'updated': path or 'all', 'exit_code': result.returncode}


@register_handler('site_settings.submodule_add')
def _submodule_add_handler(ctx, meta):
    from flask import current_app
    root   = os.path.normpath(os.path.join(current_app.root_path, '..'))
    url    = meta['url']
    path   = meta['path']
    branch = meta.get('branch', '')

    ctx.log(f"Adding submodule '{url}' at '{path}'")
    ctx.update_progress(5)
    ctx.checkpoint()

    cmd = ['git', 'submodule', 'add']
    if branch:
        cmd.extend(['-b', branch])
    cmd.extend(['--', url, path])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=root)
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        if line.strip():
            ctx.log(line, level='info' if result.returncode == 0 else 'error')

    ctx.update_progress(70)

    if result.returncode != 0:
        raise Exception(f"git submodule add failed: {result.stderr.strip()[:300]}")

    ctx.log("Initializing and updating submodule…")
    init = subprocess.run(
        ['git', 'submodule', 'update', '--init', '--', path],
        capture_output=True, text=True, timeout=300, cwd=root,
    )
    for line in (init.stdout + '\n' + init.stderr).splitlines():
        if line.strip():
            ctx.log(line, level='info' if init.returncode == 0 else 'warning')

    ctx.update_progress(100)
    ctx.log("Submodule added successfully.", level='success')
    return {'added': path, 'url': url}


@register_handler('site_settings.submodule_remove')
def _submodule_remove_handler(ctx, meta):
    from flask import current_app
    root = os.path.normpath(os.path.join(current_app.root_path, '..'))
    path = meta['path']
    name = meta.get('name', path.split('/')[-1])

    if not _validate_submodule_path(path):
        raise Exception(f"Invalid submodule path: '{path}'")

    ctx.log(f"Removing submodule '{name}' at '{path}'")
    ctx.update_progress(10)
    ctx.checkpoint()

    # Step 1: deinit
    ctx.log("Running git submodule deinit…")
    r1 = subprocess.run(
        ['git', 'submodule', 'deinit', '-f', '--', path],
        capture_output=True, text=True, timeout=60, cwd=root,
    )
    for line in (r1.stdout + '\n' + r1.stderr).splitlines():
        if line.strip():
            ctx.log(line)
    ctx.update_progress(35)
    ctx.checkpoint()

    # Step 2: git rm
    ctx.log("Running git rm…")
    r2 = subprocess.run(
        ['git', 'rm', '-f', '--', path],
        capture_output=True, text=True, timeout=60, cwd=root,
    )
    for line in (r2.stdout + '\n' + r2.stderr).splitlines():
        if line.strip():
            ctx.log(line)
    ctx.update_progress(65)
    ctx.checkpoint()

    if r2.returncode != 0:
        raise Exception(f"git rm failed: {r2.stderr.strip()[:300]}")

    # Step 3: remove from .git/modules
    git_modules_path = os.path.join(root, '.git', 'modules', name)
    if os.path.isdir(git_modules_path):
        import shutil
        ctx.log(f"Cleaning .git/modules/{name}…")
        shutil.rmtree(git_modules_path, ignore_errors=True)
    ctx.update_progress(90)

    # Step 4: remove leftover directory if still present
    full_path = os.path.join(root, path)
    if os.path.isdir(full_path):
        import shutil
        ctx.log(f"Removing leftover directory '{path}'…")
        shutil.rmtree(full_path, ignore_errors=True)

    ctx.update_progress(100)
    ctx.log(f"Submodule '{name}' removed successfully.", level='success')
    return {'removed': path}


# ── System info ───────────────────────────────────────────────────────────────

def get_system_info() -> dict:
    import flask
    from flask import current_app

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_uri_safe = re.sub(r':[^:@/]+@', ':***@', db_uri)

    key = os.environ.get('SECRET_KEY', '')
    if len(key) >= 8:
        key_preview = key[:4] + '••••••••' + key[-4:]
    elif key:
        key_preview = '••••••••'
    else:
        key_preview = 'not set'

    from ...core.utils.mailer import is_smtp_configured

    return {
        'python_version':     sys.version.split()[0],
        'flask_version':      flask.__version__,
        'platform':           f"{platform.system()} {platform.release()}",
        'debug_mode':         current_app.debug,
        'env':                os.environ.get('FLASKENV', 'development'),
        'db_uri':             db_uri_safe,
        'secret_key_preview': key_preview,
        'secret_key_set':     bool(key),
        'smtp_configured':    is_smtp_configured(),
    }
