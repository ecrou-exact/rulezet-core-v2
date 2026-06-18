from flask import Blueprint, render_template
from ...core.utils.decorators import require_permission
from ..rules.rules_core import get_formats

rules_blueprint = Blueprint('rules', __name__, template_folder='../../templates')

PLATFORMS = [
    'windows', 'linux', 'macos', 'network', 'cloud',
    'android', 'ios', 'container', 'office365', 'azure-ad',
]


@rules_blueprint.route('/')
@require_permission('rules.view', public=True)
def index():
    return render_template('rules/index.html')


@rules_blueprint.route('/<string:uuid>')
@require_permission('rules.view', public=True)
def detail(uuid):
    return render_template('rules/detail.html', rule_uuid=uuid)


@rules_blueprint.route('/create')
@rules_blueprint.route('/create/<sub>')
@require_permission(None)
def create(sub='manual'):
    if sub not in ('manual', 'github', 'file'):
        sub = 'manual'
    formats = [f.to_json_light() for f in get_formats()]
    return render_template(
        'rules/create.html',
        active_sub=sub,
        formats=formats,
        platforms=PLATFORMS,
    )
