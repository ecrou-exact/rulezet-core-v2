from flask import abort

from ...core.db_class.user import User, Role


def get_user_or_404(uid: int) -> User:
    user = User.query.get(uid)
    if not user:
        abort(404)
    return user


def get_role_or_404(role_id: int) -> Role:
    role = Role.query.get(role_id)
    if not role:
        abort(404)
    return role


def _admin_role_ids() -> list[int]:
    return [r.id for r in Role.query.filter_by(admin=True).all()]


def count_admins() -> int:
    ids = _admin_role_ids()
    if not ids:
        return 0
    return User.query.filter(User.role_id.in_(ids)).count()


def is_last_admin(user_id: int) -> bool:
    """True if user_id is the only admin-role user in the system."""
    user = User.query.get(user_id)
    if not user or not user.is_admin():
        return False
    ids = _admin_role_ids()
    return User.query.filter(
        User.role_id.in_(ids),
        User.id != user_id,
    ).count() == 0


def count_superadmins() -> int:
    return User.query.filter_by(is_superadmin=True).count()


def get_superadmins() -> list:
    return User.query.filter_by(is_superadmin=True).all()


def get_restore_email_target(triggering_user_id: int):
    """
    Returns the User who should receive the restore confirmation code.
    - 2 superadmins → the OTHER one
    - 1 superadmin  → themselves
    - 0 superadmins → first admin-role user (fallback)
    """
    superadmins = [u for u in get_superadmins() if u.is_admin()]
    if not superadmins:
        ids = _admin_role_ids()
        return User.query.filter(User.role_id.in_(ids)).first() if ids else None
    others = [u for u in superadmins if u.id != triggering_user_id]
    return others[0] if others else superadmins[0]
