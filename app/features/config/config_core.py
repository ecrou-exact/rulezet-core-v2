import os
from datetime import datetime
from flask import request, current_app
from flask_login import current_user
from ... import db
from ...core.db_class.config import UserConfig, NAV_POSITION_CHOICES, TOAST_POSITION_CHOICES, TOAST_STYLE_CHOICES, TOAST_DURATION_MIN, TOAST_DURATION_MAX
from ...core.db_class.custom_theme import CustomTheme, slugify


THEME_VAR_KEYS = [
    '--brand', '--brand-dim', '--brand-glow',
    '--bg-body', '--bg-surface', '--bg-elevated', '--bg-sidebar',
    '--text-main', '--text-secondary', '--text-muted',
    '--text-sidebar', '--text-sidebar-muted',
    '--border', '--border-subtle', '--border-sidebar',
    '--sidebar-hover', '--sidebar-active',
    '--shadow-sm', '--shadow-md', '--shadow-lg',
]

BUILTIN_STATIC_THEMES = {'system', 'light', 'dark', 'ocean', 'forest', 'midnight', 'slate', 'christmas'}
BUILTIN_OVERRIDABLE = {'dark', 'ocean', 'forest', 'midnight', 'slate'}

_BUILTIN_META = {
    'dark':     ('Dark',     'fa-moon',        True),
    'ocean':    ('Ocean',    'fa-water',        False),
    'forest':   ('Forest',   'fa-tree',         True),
    'midnight': ('Midnight', 'fa-star',         True),
    'slate':    ('Slate',    'fa-layer-group',  True),
}


def get_valid_theme_keys(admin=False):
    """Admin can select any active custom theme; others only public ones."""
    q = CustomTheme.query.filter_by(is_active=True, is_builtin=False)
    if not admin:
        q = q.filter_by(is_public=True)
    custom_keys = {t.css_key for t in q.all()}
    return BUILTIN_STATIC_THEMES | custom_keys


def get_all_custom_themes(admin_view=True):
    """Return active themes. Admin sees all; non-admin sees only public ones."""
    q = CustomTheme.query.filter_by(is_active=True)
    if not admin_view:
        q = q.filter_by(is_public=True)
    return q.order_by(CustomTheme.id).all()


def regenerate_custom_themes_css():
    themes = CustomTheme.query.filter_by(is_active=True).order_by(CustomTheme.id).all()
    lines = ['/* Auto-generated custom themes — do not edit manually */']
    for t in themes:
        if not t.css_vars:
            continue
        lines.append(f'\n[data-theme="{t.css_key}"] {{')
        for var, value in t.css_vars.items():
            if var in THEME_VAR_KEYS and value:
                lines.append(f'    {var}: {value};')
        lines.append('}')
    css = '\n'.join(lines) + '\n'
    path = os.path.join(current_app.root_path, 'static', 'css', 'themes', 'custom-themes.css')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(css)


def create_custom_theme_core(data, user_id):
    try:
        name = (data.get('name') or '').strip()
        if not name or len(name) > 64:
            return None, "Theme name is required (max 64 chars)"
        css_key = slugify(name)
        if not css_key:
            return None, "Invalid theme name"
        if css_key in BUILTIN_STATIC_THEMES:
            return None, "Cannot use a built-in theme name"
        existing = CustomTheme.query.filter_by(css_key=css_key).first()
        if existing:
            return None, "A theme with this name already exists"
        icon    = (data.get('icon') or 'fa-palette').strip()
        is_dark = bool(data.get('is_dark', False))
        css_vars = {k: v for k, v in (data.get('css_vars') or {}).items() if k in THEME_VAR_KEYS and v}
        theme = CustomTheme(
            name=name, css_key=css_key, icon=icon,
            is_dark=is_dark, is_builtin=False,
            css_vars=css_vars or None, created_by=user_id,
        )
        db.session.add(theme)
        db.session.commit()
        regenerate_custom_themes_css()
        from ...core.utils.logger import log_action
        log_action(f"Custom theme '{name}' created", "create", category="themes",
                   level="success", object_type="custom_theme", object_id=theme.id,
                   is_public=False, meta={"css_key": css_key})
        return theme, "Theme created"
    except Exception as e:
        db.session.rollback()
        return None, f"Error creating theme: {e}"


def update_custom_theme_core(uuid, data, user_id):
    try:
        theme = CustomTheme.query.filter_by(uuid=uuid, is_active=True).first()
        if not theme:
            return None, "Theme not found"
        if not theme.is_builtin:
            name = (data.get('name') or '').strip()
            if name and len(name) <= 64:
                theme.name = name
            icon = data.get('icon')
            if icon:
                theme.icon = icon.strip()
            if 'is_dark' in data:
                theme.is_dark = bool(data['is_dark'])
        if 'is_public' in data:
            theme.is_public = bool(data['is_public'])
        if 'css_vars' in data:
            css_vars = {k: v for k, v in (data['css_vars'] or {}).items() if k in THEME_VAR_KEYS and v}
            theme.css_vars = css_vars or None
        db.session.commit()
        regenerate_custom_themes_css()
        from ...core.utils.logger import log_action
        log_action(f"Theme '{theme.name}' updated", "edit", category="themes",
                   level="success", object_type="custom_theme", object_id=theme.id,
                   is_public=False)
        return theme, "Theme updated"
    except Exception as e:
        db.session.rollback()
        return None, f"Error updating theme: {e}"


def delete_custom_theme_core(uuid, user_id):
    try:
        theme = CustomTheme.query.filter_by(uuid=uuid, is_active=True).first()
        if not theme:
            return False, "Theme not found"
        if theme.is_builtin:
            return False, "Cannot delete a built-in theme override"
        theme.is_active  = False
        theme.deleted_at = datetime.utcnow()
        theme.deleted_by = user_id
        db.session.commit()
        regenerate_custom_themes_css()
        from ...core.utils.logger import log_action
        log_action(f"Theme '{theme.name}' deleted", "delete", category="themes",
                   level="success", object_type="custom_theme", object_id=theme.id,
                   is_public=False)
        return True, "Theme deleted"
    except Exception as e:
        db.session.rollback()
        return False, f"Error deleting theme: {e}"


def upsert_builtin_theme_override_core(css_key, data, user_id):
    if css_key not in BUILTIN_OVERRIDABLE:
        return None, "Not a valid built-in theme"
    try:
        theme = CustomTheme.query.filter_by(css_key=css_key, is_builtin=True).first()
        bname, bicon, bdark = _BUILTIN_META[css_key]
        if not theme:
            theme = CustomTheme(
                name=bname, css_key=css_key, icon=bicon,
                is_dark=bdark, is_builtin=True, created_by=user_id,
            )
            db.session.add(theme)
        css_vars = {k: v for k, v in (data.get('css_vars') or {}).items() if k in THEME_VAR_KEYS and v}
        theme.css_vars  = css_vars or None
        theme.is_active = bool(css_vars)
        db.session.commit()
        regenerate_custom_themes_css()
        from ...core.utils.logger import log_action
        log_action(f"Built-in theme '{css_key}' overridden", "edit", category="themes",
                   level="success", object_type="custom_theme", object_id=theme.id,
                   is_public=False)
        return theme, "Theme vars saved"
    except Exception as e:
        db.session.rollback()
        return None, f"Error saving theme: {e}"


def reset_builtin_theme_core(css_key, user_id):
    if css_key not in BUILTIN_OVERRIDABLE:
        return False, "Not a valid built-in theme"
    try:
        theme = CustomTheme.query.filter_by(css_key=css_key, is_builtin=True).first()
        if theme:
            theme.is_active = False
            theme.css_vars  = None
            db.session.commit()
            regenerate_custom_themes_css()
        return True, "Built-in theme reset to defaults"
    except Exception as e:
        db.session.rollback()
        return False, f"Error resetting theme: {e}"


def _resolve_user_id():
    """Return the authenticated user's id from session OR API key."""
    if current_user.is_authenticated:
        return current_user.id
    api_key = request.headers.get('X-API-KEY')
    if api_key:
        from ...core.utils.utils import get_user_api
        user = get_user_api(api_key)
        if user:
            return user.id
    return None


def get_user_config(user_id=None):
    uid = user_id or _resolve_user_id()
    if not uid:
        return None
    return UserConfig.query.filter_by(user_id=uid, is_active=True).first()


def create_default_config_core(user_id) -> tuple:
    try:
        existing = UserConfig.query.filter_by(user_id=user_id).first()
        if existing:
            return existing, "Config already exists"
        config = UserConfig(user_id=user_id, created_by=user_id)
        db.session.add(config)
        db.session.commit()
        return config, "Config created"
    except Exception:
        db.session.rollback()
        return None, "Error creating config"


def update_config_core(form_dict) -> tuple:
    try:
        uid = _resolve_user_id()
        config = get_user_config(uid)
        if not config:
            config, msg = create_default_config_core(uid)
            if not config:
                return None, msg

        if 'theme' in form_dict:
            uid = _resolve_user_id()
            from ...core.db_class.user import User
            user = User.query.get(uid) if uid else None
            is_admin = user.is_admin() if user else False
            if form_dict['theme'] not in get_valid_theme_keys(admin=is_admin):
                return None, "Invalid theme"
            config.theme = form_dict['theme']

        if 'nav_position' in form_dict:
            if form_dict['nav_position'] not in NAV_POSITION_CHOICES:
                return None, "Invalid nav position"
            config.nav_position = form_dict['nav_position']

        if 'sidebar_collapsed' in form_dict:
            config.sidebar_collapsed = bool(form_dict['sidebar_collapsed'])

        if 'toast_position' in form_dict:
            if form_dict['toast_position'] not in TOAST_POSITION_CHOICES:
                return None, "Invalid toast position"
            config.toast_position = form_dict['toast_position']

        if 'toast_style' in form_dict:
            if form_dict['toast_style'] not in TOAST_STYLE_CHOICES:
                return None, "Invalid toast style"
            config.toast_style = form_dict['toast_style']

        if 'toast_duration' in form_dict:
            val = int(form_dict['toast_duration'])
            if not (TOAST_DURATION_MIN <= val <= TOAST_DURATION_MAX):
                return None, f"Duration must be between {TOAST_DURATION_MIN} and {TOAST_DURATION_MAX}"
            config.toast_duration = val

        db.session.commit()
        return config, "Settings saved"
    except Exception:
        db.session.rollback()
        return None, "Error saving settings"
