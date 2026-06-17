from flask import request
from flask_restx import Namespace, Resource
from flask_login import current_user

from ..core.utils.decorators import api_require_permission

comment_ns = Namespace('comments', description='Comment system')


def _current_user_id():
    """Return current authenticated user id, or None."""
    try:
        from ..core.utils.utils import get_user_api
        api_key = request.headers.get('X-API-KEY')
        if api_key:
            from ..core.utils.utils import get_user_api as _gua
            u = _gua(api_key)
            return u.id if u else None
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def _is_admin():
    try:
        api_key = request.headers.get('X-API-KEY')
        if api_key:
            from ..core.utils.utils import get_user_api
            u = get_user_api(api_key)
            return u.is_admin() if u else False
        if current_user.is_authenticated:
            return current_user.is_admin()
    except Exception:
        pass
    return False


@comment_ns.route('')
class CommentList(Resource):

    @api_require_permission('comments.view')
    def get(self):
        """List comments for a given object."""
        object_type     = request.args.get('object_type', '').strip()
        object_id_raw   = request.args.get('object_id', '')
        parent_id_raw   = request.args.get('parent_id', None)
        page            = int(request.args.get('page', 1))
        per_page        = int(request.args.get('per_page', 20))
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'

        if not object_type or not object_id_raw:
            return {'message': 'object_type and object_id are required'}, 400

        try:
            object_id = int(object_id_raw)
        except ValueError:
            return {'message': 'object_id must be an integer'}, 400

        parent_id = None
        if parent_id_raw:
            try:
                parent_id = int(parent_id_raw)
            except ValueError:
                return {'message': 'parent_id must be an integer'}, 400

        uid          = _current_user_id()
        is_mod       = _is_admin()
        can_see_priv = is_mod

        if include_deleted and is_mod:
            from ..features.comments.comment_core import get_comments_with_deleted_core
            result = get_comments_with_deleted_core(
                object_type, object_id,
                parent_id=parent_id,
                page=page, per_page=per_page,
                current_user_id=uid,
            )
        else:
            from ..features.comments.comment_core import get_comments_core
            result = get_comments_core(
                object_type, object_id,
                parent_id=parent_id,
                page=page, per_page=per_page,
                current_user_id=uid,
                can_see_private=can_see_priv,
            )

        return result, 200

    @api_require_permission('comments.create')
    def post(self):
        """Post a new comment."""
        data = request.get_json(silent=True) or {}
        uid  = _current_user_id()
        if not uid:
            return {'message': 'Authentication required'}, 403

        from ..features.comments.comment_core import create_comment_core
        comment, msg = create_comment_core(data, uid)
        if not comment:
            return {'message': msg}, 400

        return {'message': msg, 'comment': comment.to_json(uid)}, 201


@comment_ns.route('/<string:uuid>')
class CommentDetail(Resource):

    @api_require_permission('comments.view')
    def get(self, uuid):
        """Get a single comment by UUID."""
        from ..core.db_class.comment import Comment
        comment = Comment.query.filter_by(uuid=uuid).first()
        if not comment:
            return {'message': 'Comment not found'}, 404
        uid = _current_user_id()
        return comment.to_json(uid), 200

    @api_require_permission()
    def put(self, uuid):
        """Edit a comment (owner or moderator)."""
        data    = request.get_json(silent=True) or {}
        content = data.get('content', '')
        uid     = _current_user_id()
        if not uid:
            return {'message': 'Authentication required'}, 403

        is_mod = _is_admin()
        from ..features.comments.comment_core import edit_comment_core
        comment, msg = edit_comment_core(uuid, content, uid, is_admin=is_mod)
        if not comment:
            return {'message': msg}, 400 if msg != 'Permission denied' else 403

        return {'message': msg, 'comment': comment.to_json(uid)}, 200

    @api_require_permission()
    def delete(self, uuid):
        """Soft-delete a comment (owner or moderator)."""
        uid = _current_user_id()
        if not uid:
            return {'message': 'Authentication required'}, 403

        is_mod = _is_admin()
        from ..features.comments.comment_core import delete_comment_core
        comment, msg = delete_comment_core(uuid, uid, is_admin=is_mod)
        if not comment:
            return {'message': msg}, 400 if msg != 'Permission denied' else 403

        return {'message': msg}, 200


@comment_ns.route('/<string:uuid>/react')
class CommentReact(Resource):

    @api_require_permission()
    def post(self, uuid):
        """Toggle or switch a reaction."""
        data     = request.get_json(silent=True) or {}
        reaction = data.get('reaction', '')
        uid      = _current_user_id()
        if not uid:
            return {'message': 'Authentication required'}, 403

        from ..features.comments.comment_core import react_comment_core
        result, msg = react_comment_core(uuid, uid, reaction)
        if result is None:
            return {'message': msg}, 400

        return {'message': msg, **result}, 200


@comment_ns.route('/<string:uuid>/restore')
class CommentRestore(Resource):

    @api_require_permission('comments.moderate')
    def post(self, uuid):
        """Restore a soft-deleted comment (moderator only)."""
        uid = _current_user_id()
        if not uid:
            return {'message': 'Authentication required'}, 403

        from ..features.comments.comment_core import restore_comment_core
        comment, msg = restore_comment_core(uuid, uid)
        if not comment:
            return {'message': msg}, 400

        return {'message': msg, 'comment': comment.to_json(uid)}, 200


@comment_ns.route('/stats/user/<int:user_id>')
class CommentUserStats(Resource):

    @api_require_permission('comments.view')
    def get(self, user_id):
        """Return comment activity stats for a user (last 12 months)."""
        months = int(request.args.get('months', 12))
        from ..features.comments.comment_core import get_user_comment_stats_core
        stats = get_user_comment_stats_core(user_id, months=months)
        return stats, 200
