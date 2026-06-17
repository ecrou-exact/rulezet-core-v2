import io
import os
import re
import uuid as _uuid

from flask_login import current_user
from app.core.utils.utils import generate_api_key
from ... import db
from ...core.db_class.user import User, Role


# ── Paths ─────────────────────────────────────────────────────────────────────

_AVATAR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'uploads', 'avatars'
)
_AVATAR_MAX_BYTES  = 2 * 1024 * 1024   # 2 MB
_AVATAR_MAX_DIM    = 400               # px
_AVATAR_FORMATS    = {'JPEG', 'PNG', 'WEBP', 'GIF'}


# ── Validators ────────────────────────────────────────────────────────────────

def _safe_str(value, max_len=255):
    """Strip leading/trailing whitespace, refuse control chars and oversized input."""
    if not value:
        return None
    v = str(value).strip()
    if len(v) > max_len or re.search(r'[\x00-\x1f\x7f]', v):
        return None
    return v or None


def _safe_url(value):
    v = _safe_str(value, 200)
    if v and not re.match(r'^https?://', v, re.I):
        v = 'https://' + v
    return v


def _safe_handle(value):
    v = _safe_str(value, 50)
    if v:
        v = v.lstrip('@')
        if not re.match(r'^[a-zA-Z0-9_\-\.]{1,50}$', v):
            return None
    return v


def _safe_phone(value):
    v = _safe_str(value, 25)
    if v and not re.match(r'^[\+\d\s\-\(\)\.]{7,25}$', v):
        return None
    return v


# ── Queries ───────────────────────────────────────────────────────────────────

def get_all_roles():
    return Role.query.all()


def get_user(id):
    return User.query.get(id)


def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


# ── Create ────────────────────────────────────────────────────────────────────

def _generate_verification_code() -> str:
    import secrets
    return f"{secrets.randbelow(900000) + 100000}"


def create_user_core(form_dict) -> tuple:
    from datetime import timedelta
    from ...core.db_class.site_config import get_site_bool
    try:
        verif_enabled = get_site_bool('email_verification_enabled', False)
        code          = None
        expires_at    = None

        if verif_enabled:
            from datetime import datetime as _dt
            code       = _generate_verification_code()
            expires_at = _dt.utcnow() + timedelta(minutes=30)

        user = User(
            first_name=form_dict['first_name'],
            last_name=form_dict['last_name'],
            email=form_dict['email'],
            password=form_dict['password'],
            role_id=form_dict.get('role_id', 2),
            api_key=generate_api_key(),
            is_verified=not verif_enabled,
            verification_token=code,
            verification_expires_at=expires_at,
        )
        db.session.add(user)
        db.session.commit()
        from ...core.db_class.config import UserConfig
        if not UserConfig.query.filter_by(user_id=user.id).first():
            db.session.add(UserConfig(user_id=user.id, created_by=user.id))
            db.session.commit()
        return user, "User created successfully"
    except Exception:
        db.session.rollback()
        return None, "Error creating user"


def resend_verification_core(user_id: int) -> tuple:
    from datetime import datetime, timedelta
    try:
        user = User.query.get(user_id)
        if not user:
            return None, "User not found"
        if user.is_verified:
            return user, "Account already verified"
        user.verification_token      = _generate_verification_code()
        user.verification_expires_at = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()
        return user, "New code generated"
    except Exception:
        db.session.rollback()
        return None, "Error generating new code"


def verify_user_core(user_id: int) -> tuple:
    try:
        user = User.query.get(user_id)
        if not user:
            return None, "User not found"
        user.is_verified             = True
        user.verification_token      = None
        user.verification_expires_at = None
        db.session.commit()
        return user, "Account verified"
    except Exception:
        db.session.rollback()
        return None, "Error verifying account"


def delete_expired_user_core(user_id: int) -> bool:
    return _hard_delete_user(user_id)


# ── Edit ──────────────────────────────────────────────────────────────────────

def confirm_email_change_core(user_id: int) -> tuple:
    try:
        user = User.query.get(user_id)
        if not user or not user.pending_email:
            return None, "No pending email change"
        user.email                   = user.pending_email
        user.pending_email           = None
        user.pending_email_token     = None
        user.pending_email_expires_at = None
        db.session.commit()
        return user, "Email updated"
    except Exception:
        db.session.rollback()
        return None, "Error updating email"


def cancel_email_change_core(user_id: int) -> None:
    try:
        user = User.query.get(user_id)
        if user:
            user.pending_email           = None
            user.pending_email_token     = None
            user.pending_email_expires_at = None
            db.session.commit()
    except Exception:
        db.session.rollback()


def resend_email_change_core(user_id: int) -> tuple:
    from datetime import datetime, timedelta
    try:
        user = User.query.get(user_id)
        if not user or not user.pending_email:
            return None, "No pending email change"
        user.pending_email_token      = _generate_verification_code()
        user.pending_email_expires_at = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()
        return user, "New code generated"
    except Exception:
        db.session.rollback()
        return None, "Error generating code"


def edit_user_core(form_dict, user_id) -> tuple:
    from ...core.db_class.site_config import get_site_bool
    try:
        user = get_user(user_id)
        if not user:
            return None, "User not found"

        user.first_name = form_dict.get('first_name', user.first_name)
        user.last_name  = form_dict.get('last_name',  user.last_name)

        # Email — verify if changed and verification is enabled
        new_email         = form_dict.get('email', user.email)
        email_change_pending = False
        if new_email and new_email != user.email:
            if get_site_bool('email_verification_enabled', False):
                from datetime import datetime as _dt, timedelta
                user.pending_email           = new_email
                user.pending_email_token     = _generate_verification_code()
                user.pending_email_expires_at = _dt.utcnow() + timedelta(minutes=30)
                email_change_pending = True
            else:
                user.email = new_email

        if form_dict.get('password'):
            user.password = form_dict['password']

        # Profile fields — sanitised
        if 'username_handle' in form_dict:
            handle = _safe_handle(form_dict['username_handle'])
            if handle:
                existing = User.query.filter_by(username=handle).first()
                if existing and existing.id != user_id:
                    return None, "Username already taken"
            user.username = handle

        user.bio      = _safe_str(form_dict.get('bio'),      500)
        user.phone    = _safe_phone(form_dict.get('phone'))
        user.job_title= _safe_str(form_dict.get('job_title'), 100)
        user.company  = _safe_str(form_dict.get('company'),  100)
        user.location = _safe_str(form_dict.get('location'), 100)

        # Social — sanitised
        user.website        = _safe_url(form_dict.get('website'))
        user.social_twitter = _safe_handle(form_dict.get('social_twitter'))
        user.social_github  = _safe_handle(form_dict.get('social_github'))
        user.social_linkedin= _safe_url(form_dict.get('social_linkedin'))

        db.session.commit()
        return user, "email_change_pending" if email_change_pending else "Profile updated"
    except Exception:
        db.session.rollback()
        return None, "Error updating profile"


# ── Avatar ────────────────────────────────────────────────────────────────────

def save_avatar_core(file_storage, user_id) -> tuple:
    from PIL import Image, UnidentifiedImageError

    os.makedirs(_AVATAR_DIR, exist_ok=True)

    file_data = file_storage.read()

    if len(file_data) > _AVATAR_MAX_BYTES:
        return None, "File too large (max 2 MB)"

    if len(file_data) < 8:
        return None, "Invalid file"

    try:
        # Verify it's a real image
        img = Image.open(io.BytesIO(file_data))
        img.verify()
        img = Image.open(io.BytesIO(file_data))   # re-open after verify()

        if img.format not in _AVATAR_FORMATS:
            return None, f"Format not supported (JPEG, PNG, WEBP)"

        # Convert, strip EXIF metadata, resize
        img = img.convert('RGB')
        img.thumbnail((_AVATAR_MAX_DIM, _AVATAR_MAX_DIM), Image.LANCZOS)

        # Delete old avatar file
        user = User.query.get(user_id)
        if user and user.avatar_filename:
            old_path = os.path.join(_AVATAR_DIR, user.avatar_filename)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Save with UUID filename — never trust user-supplied filename
        filename = str(_uuid.uuid4()) + '.jpg'
        img.save(os.path.join(_AVATAR_DIR, filename), 'JPEG', quality=88, optimize=True)

        user.avatar_filename = filename
        db.session.commit()
        return filename, "Avatar updated"

    except (UnidentifiedImageError, Exception):
        return None, "Invalid or corrupt image file"


def delete_avatar_core(user_id) -> tuple:
    try:
        user = User.query.get(user_id)
        if not user or not user.avatar_filename:
            return True, "No avatar to delete"
        path = os.path.join(_AVATAR_DIR, user.avatar_filename)
        if os.path.exists(path):
            os.remove(path)
        user.avatar_filename = None
        db.session.commit()
        return True, "Avatar removed"
    except Exception:
        db.session.rollback()
        return False, "Error removing avatar"


# ── API key ───────────────────────────────────────────────────────────────────

def reload_api_key_core(user_id) -> tuple:
    try:
        user = User.query.get(user_id)
        if not user:
            return None, "User not found"
        user.api_key = generate_api_key()
        db.session.commit()
        return user, "API key regenerated"
    except Exception:
        db.session.rollback()
        return None, "Error regenerating API key"


# ── Delete ────────────────────────────────────────────────────────────────────

def _hard_delete_user(user_id) -> bool:
    """Delete a user and its UserConfig. Used by both delete_user_core and delete_expired_user_core."""
    try:
        user = User.query.get(user_id)
        if not user:
            return False
        from ...core.db_class.config import UserConfig
        UserConfig.query.filter_by(user_id=user_id).delete()
        if user.avatar_filename:
            path = os.path.join(_AVATAR_DIR, user.avatar_filename)
            if os.path.exists(path):
                os.remove(path)
        db.session.delete(user)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def delete_user_core(user_id) -> bool:
    return _hard_delete_user(user_id)
