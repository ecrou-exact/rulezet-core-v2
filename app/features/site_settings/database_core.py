"""
database_core.py — DB management: info, backups, restore (email-confirmed), SQL console, history.
Superadmin-only. All operations are logged.
"""
import re
import shutil
import secrets
from datetime import datetime, timedelta
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────────────────────

def _db_path() -> Path | None:
    from flask import current_app
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if uri.startswith('sqlite:///'):
        fname = uri[10:]
        return Path(current_app.instance_path) / fname
    return None


def _backup_dir() -> Path:
    from flask import current_app
    d = Path(current_app.instance_path) / 'backups'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_backup_path(filename: str) -> Path | None:
    """Return absolute path only if filename is a valid .db inside backup dir."""
    if not filename or not re.match(r'^[\w\-]+\.db$', filename):
        return None
    p = (_backup_dir() / filename).resolve()
    if not str(p).startswith(str(_backup_dir().resolve())):
        return None
    return p


def _fmt_size(size: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ── DB Info ───────────────────────────────────────────────────────────────────

def get_db_info() -> dict:
    from flask import current_app
    from sqlalchemy import inspect, text
    from app import db

    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if 'sqlite' in uri:
        db_type = 'SQLite'
    elif 'postgresql' in uri or 'postgres' in uri:
        db_type = 'PostgreSQL'
    elif 'mysql' in uri:
        db_type = 'MySQL'
    else:
        db_type = 'Unknown'

    db_path   = _db_path()
    size_bytes = db_path.stat().st_size if db_path and db_path.exists() else 0

    tables = []
    try:
        inspector = inspect(db.engine)
        for tname in sorted(inspector.get_table_names()):
            try:
                count = db.session.execute(text(f'SELECT COUNT(*) FROM "{tname}"')).scalar()
            except Exception:
                count = -1
            tables.append({'name': tname, 'rows': int(count) if count is not None else -1})
    except Exception as exc:
        tables = [{'name': f'Error: {exc}', 'rows': -1}]

    backup_dir = _backup_dir()
    backup_count = len(list(backup_dir.glob('*.db')))

    return {
        'db_type':      db_type,
        'db_path':      str(db_path) if db_path else uri,
        'size_bytes':   size_bytes,
        'size_human':   _fmt_size(size_bytes),
        'table_count':  len(tables),
        'tables':       tables,
        'backup_count': backup_count,
        'backup_dir':   str(backup_dir),
    }


# ── Backups ───────────────────────────────────────────────────────────────────

def list_backups() -> list:
    bd = _backup_dir()
    result = []
    for f in sorted(bd.glob('*.db'), key=lambda f: f.stat().st_mtime, reverse=True):
        stat = f.stat()
        result.append({
            'filename':   f.name,
            'size_bytes': stat.st_size,
            'size_human': _fmt_size(stat.st_size),
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return result


def create_backup_core(user_id: int) -> tuple:
    from ...core.utils.logger import log_action

    db_path = _db_path()
    if db_path is None:
        return None, "Non-SQLite databases: use pg_dump externally (not yet supported via UI)"
    if not db_path.exists():
        return None, f"DB file not found: {db_path}"

    ts   = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    name = f'backup_{ts}.db'
    dest = _backup_dir() / name
    shutil.copy2(db_path, dest)
    size = dest.stat().st_size

    log_action(
        f"DB backup created: {name}",
        'create',
        category='database',
        level='success',
        object_type='db_backup',
        is_public=False,
        meta={'filename': name, 'size_bytes': size},
        actor_id=user_id,
    )
    return name, f"Backup created successfully ({_fmt_size(size)})"


def rename_backup_core(old_filename: str, new_filename: str, user_id: int) -> tuple:
    from ...core.utils.logger import log_action

    p_old = _safe_backup_path(old_filename)
    if p_old is None or not p_old.exists():
        return False, 'Backup not found.'

    new_filename = new_filename.strip()
    if not new_filename.endswith('.db'):
        new_filename += '.db'
    p_new = _safe_backup_path(new_filename)
    if p_new is None:
        return False, 'Invalid filename. Use only letters, numbers, hyphens, underscores and a .db extension.'
    if p_new.exists():
        return False, f'A backup named "{new_filename}" already exists.'

    p_old.rename(p_new)
    log_action(
        f'DB backup renamed: {old_filename} → {new_filename}',
        'edit',
        category='database',
        level='info',
        object_type='db_backup',
        is_public=False,
        meta={'old': old_filename, 'new': new_filename},
        actor_id=user_id,
    )
    return True, new_filename


def delete_backup_core(filename: str, user_id: int) -> tuple:
    from ...core.utils.logger import log_action

    p = _safe_backup_path(filename)
    if p is None:
        return False, "Invalid filename"
    if not p.exists():
        return False, "Backup not found"

    p.unlink()
    log_action(
        f"DB backup deleted: {filename}",
        'delete',
        category='database',
        level='warning',
        object_type='db_backup',
        is_public=False,
        meta={'filename': filename},
        actor_id=user_id,
    )
    return True, "Backup deleted"


# ── Generic two-step action helpers ──────────────────────────────────────────

def _initiate_action(action: str, filename: str, user_id: int) -> tuple:
    """Send a confirmation code to the superadmin for any backup action."""
    from ...core.utils.logger import log_action
    from ...core.db_class.site_config import set_site_value
    from ...features.admin.admin_core import get_restore_email_target
    from ...core.utils.mailer import is_smtp_configured

    p = _safe_backup_path(filename)
    if p is None:
        return False, "Invalid filename"
    if not p.exists():
        return False, "Backup file not found"

    if not is_smtp_configured():
        return False, "SMTP is not configured. Configure SMTP in Server Settings before performing this action — the confirmation code must be sent by email."

    target_user = get_restore_email_target(user_id)
    if not target_user:
        return False, "No admin account found to receive the confirmation code."

    code   = ''.join(secrets.choice('0123456789') for _ in range(6))
    expiry = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    set_site_value(f'db_{action}_pending_code',     code,     user_id)
    set_site_value(f'db_{action}_pending_expiry',   expiry,   user_id)
    set_site_value(f'db_{action}_pending_filename', filename, user_id)

    if action == 'restore':
        from ...core.utils.mailer import send_db_restore_confirmation
        ok, err = send_db_restore_confirmation(target_user.email, filename, code)
    else:
        from ...core.utils.mailer import send_db_action_confirmation
        ok, err = send_db_action_confirmation(target_user.email, action, filename, code)

    if not ok:
        return False, f"Failed to send confirmation email: {err}"

    log_action(
        f"DB {action} initiated for {filename}",
        f'{action}_initiate',
        category='database',
        level='warning',
        object_type='db_backup',
        is_public=False,
        meta={'filename': filename, 'action': action},
        actor_id=user_id,
    )
    return True, "Confirmation code sent to the superadmin. Valid for 10 minutes."


def _validate_action_code(action: str, filename: str, code: str, user_id: int) -> tuple:
    """Validate a pending action code. Returns (True, None) or (False, error_msg)."""
    from ...core.db_class.site_config import get_site_value, set_site_value
    from ...core.utils.logger import log_action

    stored_code     = get_site_value(f'db_{action}_pending_code')
    stored_expiry   = get_site_value(f'db_{action}_pending_expiry')
    stored_filename = get_site_value(f'db_{action}_pending_filename')

    if not stored_code:
        return False, f"No {action} pending — initiate one first."
    if stored_filename != filename:
        return False, "Filename mismatch — please re-initiate."

    try:
        if datetime.utcnow() > datetime.fromisoformat(stored_expiry):
            return False, "Code expired (10 min limit). Please re-initiate."
    except Exception:
        return False, "Invalid expiry state. Please re-initiate."

    if code.strip() != stored_code:
        log_action(
            f"DB {action} REJECTED: wrong code for {filename}",
            f'{action}_failed',
            category='database',
            level='error',
            is_public=False,
            actor_id=user_id,
        )
        return False, "Invalid confirmation code."

    set_site_value(f'db_{action}_pending_code',     '', user_id)
    set_site_value(f'db_{action}_pending_filename', '', user_id)
    return True, None


# ── Restore ───────────────────────────────────────────────────────────────────

def initiate_restore_core(filename: str, user_id: int) -> tuple:
    return _initiate_action('restore', filename, user_id)


def confirm_restore_core(filename: str, code: str, user_id: int) -> tuple:
    from ...core.utils.logger import log_action
    from app import db

    ok, err = _validate_action_code('restore', filename, code, user_id)
    if not ok:
        return False, err

    db_path = _db_path()
    p = _safe_backup_path(filename)
    if db_path is None or not p or not p.exists():
        return False, "Backup file or DB path unavailable."

    ts          = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    safety_name = f'pre_restore_{ts}.db'
    shutil.copy2(db_path, _backup_dir() / safety_name)

    db.engine.dispose()
    shutil.copy2(p, db_path)

    log_action(
        f"Database RESTORED from {filename} — safety backup: {safety_name}",
        'restore',
        category='database',
        level='error',
        object_type='db_backup',
        is_public=False,
        meta={'filename': filename, 'safety_backup': safety_name},
        actor_id=user_id,
    )
    return True, (
        f"Database restored from {filename}. "
        f"Safety backup saved as {safety_name}. "
        f"Restart the server for a clean state."
    )


# ── Delete (two-step) ─────────────────────────────────────────────────────────

def initiate_delete_core(filename: str, user_id: int) -> tuple:
    return _initiate_action('delete', filename, user_id)


def confirm_delete_core(filename: str, code: str, user_id: int) -> tuple:
    from ...core.utils.logger import log_action

    ok, err = _validate_action_code('delete', filename, code, user_id)
    if not ok:
        return False, err

    p = _safe_backup_path(filename)
    if p is None or not p.exists():
        return False, "Backup not found"

    p.unlink()
    log_action(
        f"DB backup deleted: {filename}",
        'delete',
        category='database',
        level='warning',
        object_type='db_backup',
        is_public=False,
        meta={'filename': filename},
        actor_id=user_id,
    )
    return True, "Backup deleted"


# ── Download (two-step) ───────────────────────────────────────────────────────

def initiate_download_core(filename: str, user_id: int) -> tuple:
    return _initiate_action('download', filename, user_id)


def confirm_download_core(filename: str, code: str, user_id: int) -> tuple:
    """Validate the code and return the backup path for the API to stream."""
    from ...core.utils.logger import log_action

    ok, err = _validate_action_code('download', filename, code, user_id)
    if not ok:
        return False, err

    p = _safe_backup_path(filename)
    if p is None or not p.exists():
        return False, "Backup not found"

    log_action(
        f"DB backup downloaded: {filename}",
        'download',
        category='database',
        level='info',
        object_type='db_backup',
        is_public=False,
        meta={'filename': filename},
        actor_id=user_id,
    )
    return True, str(p)


# ── SQL Console ───────────────────────────────────────────────────────────────

_DESTRUCTIVE = ('DELETE', 'DROP', 'TRUNCATE', 'UPDATE')
_READ_ONLY   = ('SELECT', 'WITH', 'EXPLAIN', 'PRAGMA')


def _classify(query: str) -> str:
    """Return 'read', 'write', or 'destructive'."""
    q = query.strip().upper().lstrip()
    if q.startswith(_READ_ONLY):
        return 'read'
    if q.startswith(_DESTRUCTIVE):
        return 'destructive'
    return 'write'


def execute_sql_core(query: str, user_id: int) -> tuple:
    from app import db
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from ...core.utils.logger import log_action

    query = query.strip()
    if not query:
        return False, "Empty query"

    kind = _classify(query)

    # Auto-backup before any destructive operation
    backup_name = None
    if kind == 'destructive':
        backup_name, _ = create_backup_core(user_id)

    try:
        result = db.session.execute(text(query))
        if kind != 'read':
            db.session.commit()

        if kind == 'read' and result.returns_rows:
            keys     = list(result.keys())
            rows_raw = result.fetchmany(500)
            rows     = [[str(v) if v is not None else None for v in row] for row in rows_raw]
            affected = len(rows)
        else:
            keys     = []
            rows     = []
            affected = result.rowcount if hasattr(result, 'rowcount') else -1

        log_action(
            f"SQL {kind.upper()} — {affected} row(s): {query[:120]}",
            'sql_query',
            category='database',
            level='info' if kind == 'read' else ('error' if kind == 'destructive' else 'warning'),
            is_public=False,
            meta={'query': query, 'rows': affected, 'kind': kind, 'backup_before': backup_name},
            actor_id=user_id,
        )
        return True, {
            'columns':       keys,
            'rows':          rows,
            'count':         affected,
            'is_read':       kind == 'read',
            'kind':          kind,
            'backup_before': backup_name,
        }

    except SQLAlchemyError as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        log_action(
            f"SQL ERROR ({kind}): {str(exc)[:200]}",
            'sql_error',
            category='database',
            level='error',
            is_public=False,
            meta={'query': query, 'error': str(exc), 'kind': kind, 'backup_before': backup_name},
            actor_id=user_id,
        )
        return False, str(exc)


# ── History ───────────────────────────────────────────────────────────────────

def get_db_history(limit: int = 100) -> list:
    from ...core.db_class.log import Log
    entries = (
        Log.query
        .filter_by(category='database')
        .order_by(Log.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id':         e.id,
            'title':      e.title,
            'action':     e.action,
            'level':      e.level,
            'created_at': e.created_at.isoformat() if e.created_at else None,
            'actor_id':   e.actor_id,
            'meta':       e.meta or {},
        }
        for e in entries
    ]


# ── Migrations ────────────────────────────────────────────────────────────────

def _alembic_cfg():
    from flask import current_app
    from alembic.config import Config
    import os
    migrations_dir = os.path.normpath(os.path.join(current_app.root_path, '..', 'migrations'))
    cfg = Config()
    cfg.set_main_option('script_location', migrations_dir)
    cfg.set_main_option('sqlalchemy.url', current_app.config['SQLALCHEMY_DATABASE_URI'])
    return cfg


def get_migration_info() -> dict:
    from flask import current_app
    from app import db
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    with db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current_heads = ctx.get_current_heads()

    script = ScriptDirectory.from_config(_alembic_cfg())

    applied = set(current_heads)
    for head in current_heads:
        for rev in script.iterate_revisions(head, 'base'):
            applied.add(rev.revision)

    revisions = []
    for rev in script.walk_revisions():
        revisions.append({
            'revision':      rev.revision,
            'down_revision': rev.down_revision if isinstance(rev.down_revision, str) else (list(rev.down_revision) if rev.down_revision else None),
            'description':   rev.doc or '',
            'applied':       rev.revision in applied,
        })

    return {
        'current_heads': list(current_heads),
        'revisions':     revisions,
        'pending_count': sum(1 for r in revisions if not r['applied']),
    }


def run_upgrade_core(user_id: int) -> tuple:
    from ...core.utils.job_runner import enqueue_job
    from ...core.utils.logger import log_action
    log_action('DB migration upgrade initiated', 'upgrade_initiate', category='database',
               level='warning', is_public=False, actor_id=user_id)
    job = enqueue_job('database.migrate_upgrade', title='DB Migration — Upgrade to head',
                      meta={}, user_id=user_id)
    return job, 'Upgrade queued'


def run_downgrade_core(revision: str, user_id: int) -> tuple:
    from ...core.utils.job_runner import enqueue_job
    from ...core.utils.logger import log_action
    if not revision or not revision.strip():
        return None, 'revision required'
    log_action(f'DB migration downgrade to {revision} initiated', 'downgrade_initiate',
               category='database', level='warning', is_public=False,
               meta={'revision': revision}, actor_id=user_id)
    job = enqueue_job('database.migrate_downgrade', title=f'DB Migration — Downgrade to {revision}',
                      meta={'revision': revision}, user_id=user_id)
    return job, f'Downgrade to {revision} queued'


# ── Migration job handlers ────────────────────────────────────────────────────

from ...core.utils.job_runner import register_handler


@register_handler('database.migrate_upgrade')
def _handle_upgrade(ctx, meta):
    from flask_migrate import upgrade as fm_upgrade
    from ...core.utils.logger import log_action
    ctx.log('Starting database upgrade to head...')
    fm_upgrade()
    ctx.log('Upgrade complete. Restart the server to reload models.')
    log_action('DB migration upgraded to head', 'upgrade', category='database',
               level='success', is_public=False)
    ctx.update_progress(100)
    return {'status': 'upgraded'}


@register_handler('database.migrate_downgrade')
def _handle_downgrade(ctx, meta):
    from flask_migrate import downgrade as fm_downgrade
    from ...core.utils.logger import log_action
    revision = meta.get('revision', '-1')
    ctx.log(f'Starting database downgrade to {revision}...')
    fm_downgrade(revision=revision)
    ctx.log(f'Downgrade to {revision} complete. Restart the server to reload models.')
    log_action(f'DB migration downgraded to {revision}', 'downgrade', category='database',
               level='warning', is_public=False, meta={'revision': revision})
    ctx.update_progress(100)
    return {'status': 'downgraded', 'revision': revision}
