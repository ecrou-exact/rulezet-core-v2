"""
comment_core.py — All business logic for the comment system.
No DB access in routes or API resources — only here.
"""
from datetime import datetime
from ... import db
from ...core.db_class.comment import Comment, CommentReaction
from ...core.utils.logger import log_action


# ── Profanity filter ──────────────────────────────────────────────────────────

def _censor(text: str) -> str:
    """Run text through better_profanity; fall back to identity if not installed."""
    try:
        from better_profanity import profanity as _p
        _p.load_censor_words()
        return _p.censor(text)
    except ImportError:
        return text


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_content(text: str) -> tuple:
    """Return (ok, cleaned_text_or_error_msg)."""
    if not text or not text.strip():
        return False, "Comment cannot be empty"
    # Strip control characters (but keep newlines/tabs)
    import re
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text.strip())
    if not cleaned:
        return False, "Comment cannot be empty"
    if len(cleaned) > 5000:
        return False, "Comment is too long (max 5000 characters)"
    return True, cleaned


# ── Read ──────────────────────────────────────────────────────────────────────

def get_comments_core(object_type, object_id, parent_id=None, page=1, per_page=20,
                      current_user_id=None, can_see_private=False) -> dict:
    """Paginated comments for a given object. Active comments only."""
    q = Comment.query.filter_by(
        object_type=object_type,
        object_id=object_id,
        is_active=True,
    )
    if parent_id is None:
        q = q.filter_by(depth=0)
    else:
        q = q.filter_by(parent_id=parent_id)

    if not can_see_private:
        q = q.filter_by(is_public=True)

    q = q.order_by(Comment.created_at.asc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'items':    [c.to_json(current_user_id) for c in paginated.items],
        'total':    paginated.total,
        'page':     paginated.page,
        'pages':    paginated.pages,
        'has_next': paginated.has_next,
        'has_prev': paginated.has_prev,
    }


def get_comments_with_deleted_core(object_type, object_id, parent_id=None, page=1,
                                    per_page=20, current_user_id=None) -> dict:
    """Admin version: includes inactive comments, shows original content."""
    q = Comment.query.filter_by(
        object_type=object_type,
        object_id=object_id,
    )
    if parent_id is None:
        q = q.filter_by(depth=0)
    else:
        q = q.filter_by(parent_id=parent_id)

    q = q.order_by(Comment.created_at.asc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'items':    [c.to_json(current_user_id, show_original=True) for c in paginated.items],
        'total':    paginated.total,
        'page':     paginated.page,
        'pages':    paginated.pages,
        'has_next': paginated.has_next,
        'has_prev': paginated.has_prev,
    }


# ── Create ────────────────────────────────────────────────────────────────────

def create_comment_core(data: dict, user_id: int) -> tuple:
    """Create a new comment. Returns (comment, msg)."""
    content_raw = data.get('content', '')
    ok, content = _validate_content(content_raw)
    if not ok:
        return None, content  # content holds the error message

    content = _censor(content)

    object_type = data.get('object_type', '').strip()
    object_id   = data.get('object_id')
    parent_id   = data.get('parent_id')
    is_public   = data.get('is_public', True)

    if not object_type or object_id is None:
        return None, "object_type and object_id are required"

    try:
        object_id = int(object_id)
    except (ValueError, TypeError):
        return None, "object_id must be an integer"

    depth   = 0
    root_id = None

    if parent_id:
        try:
            parent_id = int(parent_id)
        except (ValueError, TypeError):
            return None, "parent_id must be an integer"

        parent = Comment.query.filter_by(id=parent_id, is_active=True).first()
        if not parent:
            return None, "Parent comment not found"

        depth   = parent.depth + 1
        root_id = parent.root_id if parent.root_id else parent.id

        if depth > 4:
            return None, "Maximum reply depth reached"
    else:
        parent_id = None

    comment = Comment(
        content=content,
        object_type=object_type,
        object_id=object_id,
        parent_id=parent_id,
        depth=depth,
        root_id=root_id,
        is_public=bool(is_public),
        created_by=user_id,
    )
    db.session.add(comment)
    db.session.commit()

    # Set root_id for top-level comments to their own id
    if root_id is None:
        comment.root_id = comment.id
        db.session.commit()

    log_action(
        title="Comment created",
        action="create",
        category="comments",
        level="success",
        object_type="comment",
        object_id=comment.id,
        is_public=True,
        meta={'object_type': object_type, 'object_id': object_id, 'depth': depth},
    )

    return comment, "Comment posted"


# ── Edit ──────────────────────────────────────────────────────────────────────

def edit_comment_core(uuid: str, content: str, user_id: int, is_admin: bool = False) -> tuple:
    """Edit a comment. Only owner or admin. Returns (comment, msg)."""
    comment = Comment.query.filter_by(uuid=uuid, is_active=True).first()
    if not comment:
        return None, "Comment not found"

    if not is_admin and comment.created_by != user_id:
        return None, "Permission denied"

    ok, cleaned = _validate_content(content)
    if not ok:
        return None, cleaned

    cleaned = _censor(cleaned)
    comment.content    = cleaned
    comment.updated_at = datetime.utcnow()
    db.session.commit()

    log_action(
        title="Comment edited",
        action="edit",
        category="comments",
        level="info",
        object_type="comment",
        object_id=comment.id,
        is_public=False,
        meta={'editor_id': user_id},
    )

    return comment, "Comment updated"


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_comment_core(uuid: str, user_id: int, is_admin: bool = False) -> tuple:
    """Soft-delete a comment. Only owner or admin. Returns (comment, msg)."""
    comment = Comment.query.filter_by(uuid=uuid, is_active=True).first()
    if not comment:
        return None, "Comment not found"

    if not is_admin and comment.created_by != user_id:
        return None, "Permission denied"

    comment.content_original = comment.content
    comment.content          = "[deleted]"
    comment.is_active        = False
    comment.deleted_at       = datetime.utcnow()
    comment.deleted_by       = user_id
    db.session.commit()

    log_action(
        title="Comment deleted",
        action="delete",
        category="comments",
        level="warning",
        object_type="comment",
        object_id=comment.id,
        is_public=False,
        meta={'deleted_by': user_id},
    )

    return comment, "Comment deleted"


# ── Restore ───────────────────────────────────────────────────────────────────

def restore_comment_core(uuid: str, admin_id: int) -> tuple:
    """Restore a soft-deleted comment. Admin only. Returns (comment, msg)."""
    comment = Comment.query.filter_by(uuid=uuid, is_active=False).first()
    if not comment:
        return None, "Comment not found or already active"

    comment.content          = comment.content_original or comment.content
    comment.content_original = None
    comment.is_active        = True
    comment.deleted_at       = None
    comment.deleted_by       = None
    db.session.commit()

    log_action(
        title="Comment restored",
        action="restore",
        category="comments",
        level="success",
        object_type="comment",
        object_id=comment.id,
        is_public=False,
        meta={'restored_by': admin_id},
    )

    return comment, "Comment restored"


# ── React ─────────────────────────────────────────────────────────────────────

def react_comment_core(uuid: str, user_id: int, reaction: str) -> tuple:
    """Toggle or switch a reaction. Returns (counts_dict, msg)."""
    if reaction not in ('like', 'dislike'):
        return None, "Invalid reaction — must be 'like' or 'dislike'"

    comment = Comment.query.filter_by(uuid=uuid, is_active=True).first()
    if not comment:
        return None, "Comment not found"

    existing = CommentReaction.query.filter_by(
        comment_id=comment.id, user_id=user_id
    ).first()

    if existing:
        if existing.reaction == reaction:
            # Same reaction → toggle off
            db.session.delete(existing)
            user_reaction = None
            msg = "Reaction removed"
        else:
            # Different reaction → switch
            existing.reaction = reaction
            user_reaction     = reaction
            msg = "Reaction updated"
    else:
        new_rxn = CommentReaction(
            comment_id=comment.id,
            user_id=user_id,
            reaction=reaction,
        )
        db.session.add(new_rxn)
        user_reaction = reaction
        msg = "Reaction added"

    db.session.commit()

    return {
        'like_count':    comment.like_count,
        'dislike_count': comment.dislike_count,
        'user_reaction': user_reaction,
    }, msg


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_user_comment_stats_core(user_id: int, months: int = 12) -> list:
    """Return comment counts per month for the last N months."""
    from datetime import timedelta
    from sqlalchemy import func, extract

    now   = datetime.utcnow()
    start = now.replace(day=1) - timedelta(days=30 * (months - 1))
    # Truncate to start of that month
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.session.query(
            extract('year',  Comment.created_at).label('year'),
            extract('month', Comment.created_at).label('month'),
            func.count(Comment.id).label('count'),
        )
        .filter(
            Comment.created_by == user_id,
            Comment.created_at >= start,
        )
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )

    # Build complete month list
    result = []
    cursor = start
    counts = {(int(r.year), int(r.month)): int(r.count) for r in rows}
    for _ in range(months):
        key  = (cursor.year, cursor.month)
        label = cursor.strftime('%Y-%m')
        result.append({'month': label, 'count': counts.get(key, 0)})
        # Advance one month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    return result
