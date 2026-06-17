from flask import Blueprint, render_template
from ...core.utils.decorators import require_permission

comment_blueprint = Blueprint('comments', __name__)


@comment_blueprint.route('/', strict_slashes=False)
@require_permission('comments.view', public=True)
def forum():
    return render_template('comments/forum.html')
