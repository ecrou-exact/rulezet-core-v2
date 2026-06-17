from flask import Blueprint, render_template
from ...core.utils.decorators import require_permission

tags_blueprint = Blueprint('tags', __name__)


@tags_blueprint.route('/', strict_slashes=False)
@require_permission('tags.view')
def index():
    return render_template('tags/index.html')
