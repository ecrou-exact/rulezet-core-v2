from flask import Blueprint, render_template
from ...core.utils.decorators import require_permission

connectors_blueprint = Blueprint('connectors', __name__)


@connectors_blueprint.route('/', strict_slashes=False)
@require_permission('connectors.view')
def index():
    return render_template('connectors/index.html')
