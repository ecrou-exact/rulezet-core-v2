from flask import Blueprint, render_template
from ...core.utils.decorators import require_permission
from .rulecast_core import get_cast_info

rulecast_blueprint = Blueprint('rulecast', __name__)


@rulecast_blueprint.route('/', strict_slashes=False)
@require_permission('admin_only')
def index():
    info = get_cast_info()
    return render_template('rulecast/index.html', info=info)
