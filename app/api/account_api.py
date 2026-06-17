from datetime import datetime, timedelta

from flask import request
from flask_restx import Namespace, Resource, fields
from sqlalchemy import or_, func

from .. import db
from ..core.db_class.user import User, Role
from ..core.db_class.log import Log
from ..core.utils.decorators import api_require_permission
from ..core.utils.utils import get_user_api
from ..core.utils.logger import log_action, api_category
from ..features.account import account_core as AccountCore
from . import verification_api as VerifApi

account_ns = Namespace('account', description='User account management')

_add_model = account_ns.model('AddUser', {
    'first_name': fields.String(required=True),
    'last_name':  fields.String(required=True),
    'email':      fields.String(required=True),
    'password':   fields.String(required=True),
})

_edit_model = account_ns.model('EditUser', {
    'first_name':      fields.String,
    'last_name':       fields.String,
    'email':           fields.String,
    'bio':             fields.String,
    'phone':           fields.String,
    'job_title':       fields.String,
    'company':         fields.String,
    'location':        fields.String,
    'website':         fields.String,
    'social_twitter':  fields.String,
    'social_github':   fields.String,
    'social_linkedin': fields.String,
})


@account_ns.route('/me')
class Me(Resource):
    method_decorators = [api_require_permission()]

    def get(self):
        user = get_user_api(request.headers.get('X-API-KEY'))
        if not user:
            return {'message': 'User not found'}, 404
        return user.to_json(), 200

    @account_ns.expect(_edit_model)
    def put(self):
        if not request.json:
            return {'message': 'Please give data'}, 400
        user = get_user_api(request.headers.get('X-API-KEY'))
        verif = VerifApi.verif_edit_user(request.json, user.id)
        if 'message' in verif:
            return verif, 400
        u, msg = AccountCore.edit_user_core(verif, user.id)
        if u:
            log_action("User updated own profile", "edit", category=api_category("user"), level="info",
                       object_type="user", object_id=user.id, is_public=False,
                       meta={"user_id": user.id})
        return {'message': msg}, 200 if u else 400


@account_ns.route('/me/reload-api-key')
class ReloadApiKey(Resource):
    method_decorators = [api_require_permission()]

    def post(self):
        user = get_user_api(request.headers.get('X-API-KEY'))
        u, msg = AccountCore.reload_api_key_core(user.id)
        if u:
            log_action("API key regenerated", "api_key_reload", category=api_category("user"), level="warning",
                       object_type="user", object_id=user.id, is_public=False,
                       meta={"user_id": user.id})
            return {'message': msg, 'api_key': u.api_key}, 200
        return {'message': msg}, 400


@account_ns.route('/user/<int:uid>')
class GetUser(Resource):
    method_decorators = [api_require_permission("users.view")]

    def get(self, uid):
        user = AccountCore.get_user(uid)
        if user:
            return user.to_json(), 200
        return {'message': 'User not found'}, 404


@account_ns.route('/add_user')
class AddUser(Resource):
    # public — no api_required so admin can create users from external tools
    @account_ns.expect(_add_model)
    def post(self):
        if not request.json:
            return {'message': 'Please give data'}, 400
        verif = VerifApi.verif_add_user(request.json)
        if 'message' in verif:
            return verif, 400
        user, _ = AccountCore.create_user_core(verif)
        if user:
            log_action("User created via API", "create", category=api_category("admin"), level="success",
                       object_type="user", object_id=user.id, is_public=False,
                       meta={"user_id": user.id})
            return {'message': 'User created', 'id': user.id}, 201
        return {'message': 'Error creating user'}, 400


@account_ns.route('/edit_user/<int:uid>')
class EditUser(Resource):
    method_decorators = [api_require_permission("users.edit")]

    @account_ns.expect(_edit_model)
    def put(self, uid):
        if not request.json:
            return {'message': 'Please give data'}, 400
        if not AccountCore.get_user(uid):
            return {'message': 'User not found'}, 404
        verif = VerifApi.verif_edit_user(request.json, uid)
        if 'message' in verif:
            return verif, 400
        u, msg = AccountCore.edit_user_core(verif, uid)
        if u:
            log_action("User edited via API", "edit", category=api_category("admin"), level="info",
                       object_type="user", object_id=uid, is_public=False,
                       meta={"user_id": uid})
        return {'message': msg}, 200 if u else 400


@account_ns.route('/delete_user/<int:uid>')
class DeleteUser(Resource):
    method_decorators = [api_require_permission("users.delete")]

    def delete(self, uid):
        from ..features.admin.admin_core import is_last_admin
        caller = get_user_api(request.headers.get('X-API-KEY'))
        if caller and caller.id == uid:
            return {'message': 'Cannot delete your own account'}, 403
        user = AccountCore.get_user(uid)
        if not user:
            return {'message': 'User not found'}, 404
        if user.is_admin():
            return {'message': 'Cannot delete an admin account. Change their role to a non-admin role first.'}, 403
        if is_last_admin(uid):
            return {'message': 'Cannot delete the last admin. Assign another admin first.'}, 403
        ok = AccountCore.delete_user_core(uid)
        if ok:
            log_action("User deleted", "delete", category=api_category("admin"), level="warning",
                       object_type="user", object_id=uid, is_public=False,
                       meta={"user_id": uid})
        return {'message': 'User deleted' if ok else 'Error'}, 200 if ok else 400


@account_ns.route('/users')
class ListUsers(Resource):
    """Paginated list of all users — admin only."""
    method_decorators = [api_require_permission("users.view")]

    _ALLOWED_SORTS = {'id', 'first_name', 'last_name', 'email', 'created_at', 'role_id'}

    def get(self):
        # ── Query params ────────────────────────────────────────────────
        try:
            page     = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(1, int(request.args.get('per_page', 10))))
        except (TypeError, ValueError):
            page, per_page = 1, 10

        search   = (request.args.get('search') or '').strip()
        sort_key = request.args.get('sort', 'id')
        sort_dir = request.args.get('dir', 'asc')

        if sort_key not in self._ALLOWED_SORTS:
            sort_key = 'id'
        if sort_dir not in ('asc', 'desc'):
            sort_dir = 'asc'

        # ── Query ────────────────────────────────────────────────────────
        q = db.session.query(User)

        if search:
            like = f'%{search}%'
            q = q.filter(or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.username.ilike(like),
            ))

        sort_col = getattr(User, sort_key)
        q = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())

        total       = q.count()
        total_pages = max(1, (total + per_page - 1) // per_page)
        page        = min(page, total_pages)
        users       = q.offset((page - 1) * per_page).limit(per_page).all()

        # ── Serialise ────────────────────────────────────────────────────
        def _role(user):
            r = Role.query.get(user.role_id) if user.role_id else None
            if not r:
                return None
            return {'id': r.id, 'name': r.name, 'admin': r.admin,
                    'color': r.color or 'gray', 'icon': r.icon or 'fa-user'}

        from datetime import datetime, timedelta
        online_threshold = datetime.utcnow() - timedelta(minutes=10)

        items = []
        for u in users:
            role = _role(u)
            items.append({
                'id':              u.id,
                'first_name':      u.first_name,
                'last_name':       u.last_name,
                'email':           u.email,
                'username':        u.username,
                'role_id':         u.role_id,
                'role_name':       role['name']  if role else None,
                'role_color':      role['color'] if role else 'gray',
                'role_icon':       role['icon']  if role else 'fa-user',
                'is_admin':        role['admin'] if role else False,
                'is_superadmin':   u.is_superadmin,
                'avatar_filename': u.avatar_filename,
                'created_at':      u.created_at.isoformat() if u.created_at else None,
                'bio':             u.bio,
                'job_title':       u.job_title,
                'company':         u.company,
                'location':        u.location,
                'is_verified':     u.is_verified,
                'is_connected':    bool(u.last_seen_at and u.last_seen_at >= online_threshold),
                'last_seen_at':    u.last_seen_at.isoformat() if u.last_seen_at else None,
            })

        return {
            'items':       items,
            'total':       total,
            'page':        page,
            'per_page':    per_page,
            'total_pages': total_pages,
        }, 200


@account_ns.route('/<int:uid>/toggle-verified')
class ToggleVerified(Resource):
    method_decorators = [api_require_permission("users.edit")]

    def post(self, uid):
        user = AccountCore.get_user(uid)
        if not user:
            return {'message': 'User not found'}, 404
        user.is_verified = not user.is_verified
        db.session.commit()
        log_action(
            f"User verification toggled to {user.is_verified}",
            "toggle_verified",
            category=api_category("admin"),
            level="info",
            object_type="user",
            object_id=uid,
            is_public=False,
            meta={"user_id": uid, "is_verified": user.is_verified},
        )
        return {'is_verified': user.is_verified, 'message': 'Updated'}, 200


@account_ns.route('/<int:uid>/toggle-superadmin')
class ToggleSuperadmin(Resource):
    method_decorators = [api_require_permission("admin_only")]

    def post(self, uid):
        from flask_login import current_user as cu
        from ..features.admin.admin_core import count_superadmins

        if not cu.is_authenticated or not cu.is_superadmin:
            return {'message': 'Only superadmins can manage superadmin status'}, 403

        user = User.query.get(uid)
        if not user:
            return {'message': 'User not found'}, 404
        if not user.is_admin():
            return {'message': 'User must have an admin role to be granted superadmin status'}, 400

        if not user.is_superadmin:
            if count_superadmins() >= 2:
                return {'message': 'Maximum 2 superadmins allowed'}, 400

        user.is_superadmin = not user.is_superadmin
        db.session.commit()
        log_action(
            f"Superadmin {'granted to' if user.is_superadmin else 'revoked from'} user #{uid}",
            "toggle_superadmin",
            category=api_category("admin"),
            level="warning",
            object_type="user",
            object_id=uid,
            is_public=False,
            meta={"user_id": uid, "is_superadmin": user.is_superadmin},
        )
        return {'is_superadmin': user.is_superadmin, 'message': 'Updated'}, 200


@account_ns.route('/<int:uid>/disconnect')
class DisconnectUser(Resource):
    method_decorators = [api_require_permission("users.edit")]

    def post(self, uid):
        user = AccountCore.get_user(uid)
        if not user:
            return {'message': 'User not found'}, 404
        user.force_logout = True
        db.session.commit()
        log_action(
            "User force-disconnected by admin",
            "force_disconnect",
            category=api_category("admin"),
            level="warning",
            object_type="user",
            object_id=uid,
            is_public=False,
            meta={"user_id": uid},
        )
        return {'message': 'User disconnected'}, 200


@account_ns.route('/bulk-verify')
class BulkVerify(Resource):
    method_decorators = [api_require_permission("users.edit")]

    def post(self):
        data = request.get_json(silent=True) or {}
        ids      = data.get('ids', [])
        verified = bool(data.get('verified', True))
        if not ids:
            return {'message': 'No ids provided'}, 400
        User.query.filter(User.id.in_(ids)).update(
            {'is_verified': verified}, synchronize_session=False
        )
        db.session.commit()
        log_action("Bulk verify users", "bulk_verify", category=api_category("admin"), level="info",
                   object_type="user", is_public=False,
                   meta={"ids": ids, "verified": verified})
        return {'message': f'Updated {len(ids)} user(s)'}, 200


@account_ns.route('/bulk-disconnect')
class BulkDisconnect(Resource):
    method_decorators = [api_require_permission("users.edit")]

    def post(self):
        data = request.get_json(silent=True) or {}
        ids = data.get('ids', [])
        if not ids:
            return {'message': 'No ids provided'}, 400
        User.query.filter(User.id.in_(ids)).update(
            {'force_logout': True}, synchronize_session=False
        )
        db.session.commit()
        log_action("Bulk disconnect users", "bulk_disconnect", category=api_category("admin"), level="warning",
                   object_type="user", is_public=False,
                   meta={"ids": ids})
        return {'message': f'Disconnected {len(ids)} user(s)'}, 200


@account_ns.route('/roles')
class ListRoles(Resource):
    """List all roles — admin required."""
    method_decorators = [api_require_permission("users.view")]

    def get(self):
        roles = AccountCore.get_all_roles()
        return [r.to_json() for r in roles], 200


@account_ns.route('/admin/user/<int:uid>')
class AdminEditUser(Resource):
    """Admin endpoint to edit any user's fields."""
    method_decorators = [api_require_permission("users.edit")]

    def put(self, uid):
        user = AccountCore.get_user(uid)
        if not user:
            return {'message': 'User not found'}, 404

        data = request.get_json(silent=True) or {}
        if not data:
            return {'message': 'No data provided'}, 400

        import re
        _EMAIL_RE  = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
        _HANDLE_RE = re.compile(r'^[a-zA-Z0-9_\-\.]{1,50}$')

        # first_name
        if 'first_name' in data:
            v = str(data['first_name']).strip()[:64] if data['first_name'] else None
            if not v:
                return {'message': 'first_name cannot be empty'}, 400
            user.first_name = v

        # last_name
        if 'last_name' in data:
            v = str(data['last_name']).strip()[:64] if data['last_name'] else None
            if not v:
                return {'message': 'last_name cannot be empty'}, 400
            user.last_name = v

        # email
        if 'email' in data:
            email = str(data['email']).strip()[:128] if data['email'] else None
            if not email:
                return {'message': 'email cannot be empty'}, 400
            if not _EMAIL_RE.match(email):
                return {'message': 'Invalid email format'}, 400
            conflict = User.query.filter_by(email=email).first()
            if conflict and conflict.id != uid:
                return {'message': 'Email already in use'}, 400
            user.email = email

        # username
        if 'username' in data:
            raw = data['username']
            if raw:
                handle = str(raw).strip().lstrip('@')[:50]
                if not _HANDLE_RE.match(handle):
                    return {'message': 'Invalid username format'}, 400
                conflict = User.query.filter_by(username=handle).first()
                if conflict and conflict.id != uid:
                    return {'message': 'Username already taken'}, 400
                user.username = handle
            else:
                user.username = None

        # role_id
        if 'role_id' in data:
            rid = data['role_id']
            if rid is not None:
                from ..features.admin.admin_core import is_last_admin
                role = Role.query.get(int(rid))
                if not role:
                    return {'message': 'Role not found'}, 400
                if user.is_admin() and not role.admin and is_last_admin(uid):
                    return {'message': 'Cannot downgrade the last admin. Assign another admin first.'}, 403
                user.role_id = role.id
                if not role.admin:
                    user.is_superadmin = False

        # is_verified
        if 'is_verified' in data:
            user.is_verified = bool(data['is_verified'])

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {'message': 'Database error'}, 500

        log_action(
            "Admin edited user",
            "admin_edit_user",
            category=api_category("admin"),
            level="info",
            object_type="user",
            object_id=uid,
            is_public=False,
            meta={
                'user_id': uid,
                'role_id': user.role_id,
                'is_verified': user.is_verified,
            },
        )

        # Build an enriched response (consistent with ListUsers format)
        role_obj = Role.query.get(user.role_id) if user.role_id else None
        return {
            'id':              user.id,
            'first_name':      user.first_name,
            'last_name':       user.last_name,
            'email':           user.email,
            'username':        user.username,
            'role_id':         user.role_id,
            'role_name':       role_obj.name             if role_obj else None,
            'role_color':      role_obj.color or 'gray'  if role_obj else 'gray',
            'role_icon':       role_obj.icon  or 'fa-user' if role_obj else 'fa-user',
            'is_admin':        role_obj.admin             if role_obj else False,
            'is_superadmin':   user.is_superadmin,
            'is_verified':     user.is_verified,
            'avatar_filename': user.avatar_filename,
            'bio':             user.bio,
            'job_title':       user.job_title,
            'company':         user.company,
            'location':        user.location,
            'created_at':      user.created_at.isoformat() if user.created_at else None,
            'last_seen_at':    user.last_seen_at.isoformat() if user.last_seen_at else None,
        }, 200


@account_ns.route('/user-activity/<int:uid>')
class UserActivity(Resource):
    """30-day activity chart data for a user — admin only."""
    method_decorators = [api_require_permission("users.view")]

    def get(self, uid):
        user = AccountCore.get_user(uid)
        if not user:
            return {'message': 'User not found'}, 404

        today     = datetime.utcnow().date()
        since     = datetime(today.year, today.month, today.day) - timedelta(days=29)

        # Group log entries by day for this actor
        rows = (
            db.session.query(
                func.strftime('%Y-%m-%d', Log.created_at).label('day'),
                func.count(Log.id).label('cnt'),
            )
            .filter(Log.actor_id == uid, Log.created_at >= since)
            .group_by('day')
            .all()
        )
        counts_by_day = {r.day: r.cnt for r in rows}

        # Build complete 30-day series (zero-fill missing days)
        daily = []
        for i in range(30):
            day_str = (since.date() + timedelta(days=i)).isoformat()
            daily.append({'date': day_str, 'count': counts_by_day.get(day_str, 0)})

        # Total events & logins
        total_events = sum(r.cnt for r in rows)

        login_count = (
            db.session.query(func.count(Log.id))
            .filter(
                Log.actor_id == uid,
                Log.created_at >= since,
                Log.action.in_(['login', 'user_login']),
            )
            .scalar() or 0
        )

        return {
            'daily':        daily,
            'total_events': total_events,
            'total_logins': login_count,
            'last_seen':    user.last_seen_at.isoformat() if user.last_seen_at else None,
        }, 200
