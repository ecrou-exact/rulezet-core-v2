from flask import request
from flask_restx import Namespace, Resource

from .. import db
from ..core.db_class.user import Role, RolePermission, User
from ..core.utils.decorators import api_require_permission
from ..core.utils.logger import log_action, api_category
from ..core.utils.permissions import all_keys

role_ns = Namespace('roles', description='Role and permission management — admin only')


@role_ns.route('/')
class RoleList(Resource):
    method_decorators = [api_require_permission("admin.roles")]

    def get(self):
        try:
            page     = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(1, int(request.args.get('per_page', 25))))
        except (TypeError, ValueError):
            page, per_page = 1, 25

        search   = (request.args.get('search') or '').strip()
        sort_key = request.args.get('sort', 'id')
        sort_dir = request.args.get('dir', 'asc')

        allowed_sorts = {'id', 'name'}
        if sort_key not in allowed_sorts:
            sort_key = 'id'
        if sort_dir not in ('asc', 'desc'):
            sort_dir = 'asc'

        q = Role.query
        if search:
            q = q.filter(Role.name.ilike(f'%{search}%'))

        sort_col = getattr(Role, sort_key)
        q = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())

        total       = q.count()
        total_pages = max(1, (total + per_page - 1) // per_page)
        page        = min(page, total_pages)
        roles       = q.offset((page - 1) * per_page).limit(per_page).all()

        return {
            'items':       [r.to_json() for r in roles],
            'total':       total,
            'page':        page,
            'per_page':    per_page,
            'total_pages': total_pages,
        }, 200

    def post(self):
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()[:64]
        if not name:
            return {'message': 'Name is required'}, 400
        if Role.query.filter_by(name=name).first():
            return {'message': 'A role with this name already exists'}, 400

        role = Role(
            name=name,
            description=(data.get('description') or '').strip()[:255] or None,
            admin=bool(data.get('admin', False)),
            read_only=bool(data.get('read_only', False)),
            color=(data.get('color') or 'gray')[:32],
            icon=(data.get('icon') or 'fa-user')[:64],
        )
        db.session.add(role)
        db.session.flush()

        _set_permissions(role, data.get('permissions', []))
        db.session.commit()

        log_action("Role created", "create", category=api_category("admin"), level="success",
                   object_type="role", object_id=role.id, is_public=False,
                   meta={"role_id": role.id, "name": role.name})
        return role.to_json(), 201


@role_ns.route('/<int:role_id>')
class RoleDetail(Resource):
    method_decorators = [api_require_permission("admin.roles")]

    def get(self, role_id):
        role = Role.query.get_or_404(role_id)
        return role.to_json(), 200

    def put(self, role_id):
        role = Role.query.get_or_404(role_id)
        data = request.get_json(silent=True) or {}

        name = (data.get('name') or '').strip()[:64]
        if not name:
            return {'message': 'Name is required'}, 400
        conflict = Role.query.filter_by(name=name).first()
        if conflict and conflict.id != role_id:
            return {'message': 'A role with this name already exists'}, 400

        role.name        = name
        role.description = (data.get('description') or '').strip()[:255] or None
        role.admin       = bool(data.get('admin', False))
        role.read_only   = bool(data.get('read_only', False))
        role.color       = (data.get('color') or 'gray')[:32]
        role.icon        = (data.get('icon') or 'fa-user')[:64]

        _set_permissions(role, data.get('permissions', []))
        db.session.commit()

        log_action("Role updated", "edit", category=api_category("admin"), level="info",
                   object_type="role", object_id=role_id, is_public=False,
                   meta={"role_id": role_id})
        return role.to_json(), 200

    def delete(self, role_id):
        role = Role.query.get_or_404(role_id)

        if role.protected:
            return {'message': f'Role "{role.name}" is protected and cannot be deleted.'}, 403

        # Reassign users that had this role to the Read Only role
        fallback = Role.query.filter_by(name='Read Only').first()
        if not fallback:
            fallback = Role.query.filter_by(read_only=True, protected=True).first()
        if not fallback:
            fallback = Role.query.filter(Role.id != role_id).first()

        if fallback:
            User.query.filter_by(role_id=role_id).update(
                {'role_id': fallback.id}, synchronize_session=False
            )

        db.session.delete(role)
        db.session.commit()

        log_action("Role deleted", "delete", category=api_category("admin"), level="warning",
                   object_type="role", object_id=role_id, is_public=False,
                   meta={"role_id": role_id, "name": role.name,
                         "fallback_role_id": fallback.id if fallback else None})
        return {'message': 'Role deleted'}, 200


@role_ns.route('/permissions')
class PermissionList(Resource):
    """List all available permission keys defined in permissions.py."""
    method_decorators = [api_require_permission("admin.roles")]

    def get(self):
        from ..core.utils.permissions import get_by_group
        return get_by_group(), 200


def _set_permissions(role: Role, keys: list) -> None:
    valid = set(all_keys())
    RolePermission.query.filter_by(role_id=role.id).delete()
    for key in keys:
        if key in valid:
            db.session.add(RolePermission(role_id=role.id, permission=key))
