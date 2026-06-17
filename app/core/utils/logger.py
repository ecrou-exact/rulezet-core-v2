"""
logger.py — Central log_action helper.

Usage:
    from app.core.utils.logger import log_action

    log_action("User logged in", "login", category="user", level="success",
               object_type="user", object_id=user.id, is_public=False,
               meta={"email": user.email})

This function is safe to call from anywhere (routes, cores, CLI scripts).
It will never raise — all exceptions are silently swallowed so a logging
failure can never break the main request flow.
"""

from __future__ import annotations


def api_category(ui_category: str = 'admin') -> str:
    """Return 'api' if the request carries X-API-KEY, else ui_category.

    Use this in API endpoints to distinguish external API calls from
    internal UI calls made via session auth (no API key).
    """
    try:
        from flask import request
        return 'api' if request.headers.get('X-API-KEY') else ui_category
    except Exception:
        return ui_category


def log_action(
    title: str,
    action: str,
    category: str = 'system',
    level: str = 'info',
    description: str | None = None,
    object_type: str | None = None,
    object_id=None,
    is_public: bool = False,
    meta: dict | None = None,
    actor_id: int | None = None,   # explicit override — auto-detected from current_user otherwise
) -> None:
    """Create and persist a Log entry.

    Parameters
    ----------
    title        Short human-readable summary (required).
    action       Machine-readable action key, e.g. "login", "create", "bulk_delete".
    category     One of: user | system | security | admin | api   (default: system).
    level        One of: info | success | warning | error          (default: info).
    description  Optional long description / detail text.
    object_type  Model name the action targets, e.g. "user", "item".
    object_id    PK / UUID of the target object.
    is_public    When True, all authenticated users can see it; False = admin only.
    meta         Arbitrary dict for extra structured data (IDs only — no plain names).
    actor_id     Override the actor. When None the current Flask-Login user is used.
    """
    try:
        from ... import db
        from ..db_class.log import Log

        # ── Detect actor ────────────────────────────────────────────────────────
        resolved_actor_id = actor_id
        if resolved_actor_id is None:
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    resolved_actor_id = current_user.id
            except Exception:
                pass

        # ── Detect IP & User-Agent ──────────────────────────────────────────────
        ip_address = None
        user_agent = None
        try:
            from flask import request, has_request_context
            if has_request_context():
                ip_address = (
                    request.headers.get('X-Forwarded-For', request.remote_addr) or ''
                ).split(',')[0].strip()
                ua = request.headers.get('User-Agent', '')
                user_agent = ua[:256] if ua else None
        except Exception:
            pass

        # ── Coerce object_id to string ──────────────────────────────────────────
        oid = str(object_id) if object_id is not None else None

        log = Log(
            title=title,
            action=action,
            category=category,
            level=level,
            description=description,
            object_type=object_type,
            object_id=oid,
            actor_id=resolved_actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_public=is_public,
            meta=meta,
        )
        db.session.add(log)
        db.session.commit()

    except Exception:
        # Never let a logging error break the application
        pass
