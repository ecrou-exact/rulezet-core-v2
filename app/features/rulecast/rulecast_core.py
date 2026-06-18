"""rulecast_core.py — Business logic for the RuleCast admin section."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

from ... import db
from ...core.db_class.rule import FormatRule
from ...core.utils.logger import log_action
from ...core.utils.rulecast import get_rulecast_info, get_formats_for_db, KNOWN_FORMATS


_KNOWN_FORMAT_NAMES = {f['name'].lower() for f in KNOWN_FORMATS}


def get_cast_info() -> dict:
    """Return cached RuleCast submodule metadata."""
    return get_rulecast_info()


def validate_rule_with_cast(format_name: str, content: str) -> dict | None:
    """
    Call RuleCast's validator via subprocess for the given format and rule content.

    Returns a dict:
        {ok, format, total, valid, invalid, rules: [{name, ok, errors, warnings}]}
    or None when RuleCast is unavailable or the format has no parser.

    Never raises — caller can always proceed if this returns None.
    """
    if not content or not content.strip():
        return None

    if format_name.lower() not in _KNOWN_FORMAT_NAMES:
        return None

    info = get_rulecast_info()
    if not info.get('available'):
        return None

    cast_dir = info.get('cast_exec_dir') or info['path']
    python   = info.get('python_path') or sys.executable

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.tmp', prefix='rulecast_')
    try:
        with os.fdopen(tmp_fd, 'w') as fh:
            fh.write(content)

        proc = subprocess.run(
            [python, 'main.py', 'validate', '-i', tmp_path,
             '-f', format_name.lower(), '--json'],
            cwd=cast_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = proc.stdout.strip()
        if not stdout:
            return None
        # stdout may have ANSI spinner noise before the JSON line
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith('{'):
                return json.loads(line)
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def import_formats_from_cast(user_id: int) -> dict:
    """
    Upsert FormatRule rows from the RuleCast formats manifest.
    Returns {created, updated, errors}.
    """
    formats = get_formats_for_db()
    created = updated = 0
    errors = []

    for fmt in formats:
        try:
            existing = FormatRule.query.filter_by(name=fmt['name']).first()
            if existing:
                existing.description     = fmt['description']
                existing.file_extension  = fmt['file_extension']
                existing.icon            = fmt['icon']
                existing.color           = fmt['color']
                existing.can_be_executed = fmt['can_be_executed']
                existing.is_builtin      = True
                existing.is_active       = True
                existing.updated_at      = datetime.utcnow()
                updated += 1
            else:
                db.session.add(FormatRule(
                    name             = fmt['name'],
                    description      = fmt['description'],
                    file_extension   = fmt['file_extension'],
                    icon             = fmt['icon'],
                    color            = fmt['color'],
                    can_be_executed  = fmt['can_be_executed'],
                    is_builtin       = True,
                    is_active        = True,
                ))
                created += 1
        except Exception as exc:
            errors.append(f"{fmt['name']}: {exc}")

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return {'created': 0, 'updated': 0, 'errors': [str(exc)]}

    log_action(
        title=f"RuleCast formats imported — {created} created, {updated} updated",
        action="bulk_import",
        category="rulecast",
        level="success" if not errors else "warning",
        object_type="format_rule",
        is_public=False,
        meta={"created": created, "updated": updated, "errors": errors},
    )

    return {'created': created, 'updated': updated, 'errors': errors}
