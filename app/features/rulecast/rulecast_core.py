"""rulecast_core.py — Business logic for the RuleCast admin section."""
from datetime import datetime

from ... import db
from ...core.db_class.rule import FormatRule
from ...core.utils.logger import log_action
from ...core.utils.rulecast import get_rulecast_info, get_formats_for_db


def get_cast_info() -> dict:
    """Return cached RuleCast submodule metadata."""
    return get_rulecast_info()


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
