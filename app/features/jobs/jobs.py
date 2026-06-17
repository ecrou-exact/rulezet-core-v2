from flask import Blueprint, render_template, abort
from ...core.utils.decorators import require_permission
from .jobs_core import get_job_or_none

jobs_blueprint = Blueprint('jobs', __name__)


@jobs_blueprint.route('/')
@require_permission('jobs.view')
def index():
    return render_template('jobs/index.html')


@jobs_blueprint.route('/<string:uuid>')
@require_permission('jobs.view')
def detail(uuid):
    job = get_job_or_none(uuid)
    if not job:
        abort(404)
    return render_template('jobs/detail.html', job=job)
