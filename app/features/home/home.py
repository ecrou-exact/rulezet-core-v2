from flask import Blueprint, render_template
from app.core.utils.decorators import require_permission

home_blueprint = Blueprint(
    'home',
    __name__,
    template_folder='templates',
    static_folder='static'
)

@home_blueprint.route("/")
def home():
    return render_template("home.html")

@home_blueprint.route("/docs")
@require_permission()
def docs():
    return render_template("docs/docs.html")


@home_blueprint.route("/lab/components")
@require_permission(None, public=True)
def lab_components():
    return render_template("lab/components.html")
