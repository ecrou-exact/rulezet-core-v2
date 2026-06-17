from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session

from config import config as Config
import os


db = SQLAlchemy()
csrf = CSRFProtect()
migrate = Migrate()
login_manager = LoginManager()
sess = Session()

def create_app():
    app = Flask(__name__)
    config_name = os.environ.get("FLASKENV")

    app.config.from_object(Config[config_name])

    Config[config_name].init_app(app)

    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.login_view = "account.login"
    login_manager.init_app(app)
    app.config["SESSION_SQLALCHEMY"] = db
    sess.init_app(app)

    from .features.home.home import home_blueprint
    from .features.account.account import account_blueprint
    from .features.config.config import config_blueprint
    from .features.admin.admin import admin_blueprint
    from .features.site_settings.site_settings import site_settings_blueprint
    from .features.comments.comment import comment_blueprint
    from .features.jobs.jobs import jobs_blueprint
    from .features.template_studio.template_studio import template_studio_blueprint
    from .features.dynamic_pages.dynamic_pages import dynamic_pages_blueprint
    from .features.tags.tags import tags_blueprint
    from .features.connectors.connectors import connectors_blueprint
    app.register_blueprint(home_blueprint, url_prefix="/")
    app.register_blueprint(account_blueprint, url_prefix="/account")
    app.register_blueprint(config_blueprint, url_prefix="/")
    app.register_blueprint(admin_blueprint, url_prefix="/admin")
    app.register_blueprint(site_settings_blueprint, url_prefix="/admin/settings")
    app.register_blueprint(comment_blueprint, url_prefix="/comments")
    app.register_blueprint(jobs_blueprint, url_prefix="/jobs")
    app.register_blueprint(template_studio_blueprint, url_prefix="/admin/template-studio")
    app.register_blueprint(dynamic_pages_blueprint, url_prefix="/pages")
    app.register_blueprint(tags_blueprint, url_prefix="/tags")
    app.register_blueprint(connectors_blueprint, url_prefix="/connectors")

    from .api.api import api_blueprint
    csrf.exempt(api_blueprint)
    app.register_blueprint(api_blueprint)

    # Ensure these tables are known to Alembic
    from .core.db_class.config import UserConfig           # noqa: F401
    from .core.db_class.site_config import SiteConfig      # noqa: F401
    from .core.db_class.log import Log                     # noqa: F401
    from .core.db_class.user import RolePermission         # noqa: F401
    from .core.db_class.comment import Comment, CommentReaction        # noqa: F401
    from .core.db_class.custom_theme import CustomTheme               # noqa: F401
    from .core.db_class.job import Job                                 # noqa: F401
    from .core.db_class.page_definition import PageDefinition         # noqa: F401
    from .core.db_class.tag import Tag                                # noqa: F401
    from .core.db_class.connector import Connector                    # noqa: F401
    from .features.connectors import connectors_core                  # noqa: F401 — registers job handlers

    @app.context_processor
    def inject_site_config():
        from .core.db_class.site_config import get_site_bool
        return dict(
            allow_registration=get_site_bool('allow_registration', True),
            allow_login=get_site_bool('allow_login', True),
            weather_widget_enabled=get_site_bool('weather_widget_enabled', False),
        )

    @app.context_processor
    def inject_user_config():
        from flask_login import current_user
        from .core.db_class.config import UserConfig as UC
        config = None
        if current_user.is_authenticated:
            config = UC.query.filter_by(user_id=current_user.id, is_active=True).first()
        return dict(user_config=config)

    @app.context_processor
    def inject_user_permissions():
        from flask_login import current_user
        from .core.utils.nav_registry import get_nav_for_user
        from .core.db_class.page_definition import PageDefinition as PD
        if current_user.is_authenticated:
            is_admin = current_user.is_admin()
            perms    = current_user.role.permission_keys() if current_user.role else []
        else:
            is_admin = False
            perms    = []
        nav_items = get_nav_for_user(is_admin, perms, is_authenticated=current_user.is_authenticated)
        # Inject dynamic pages (Template Studio published pages) into the nav
        try:
            for page in PD.query.filter_by(is_active=True, is_published=True).all():
                if not page.nav_group:
                    continue
                p = page.required_permission
                visible = (p is None or is_admin or (p != 'admin_only' and p in perms))
                if visible:
                    nav_items.append({
                        'group':      page.nav_group,
                        'label':      page.nav_label or page.name,
                        'icon':       page.nav_icon or 'fa-file',
                        'href':       f'/pages/{page.slug}',
                        'permission': p,
                    })
        except Exception:
            pass
        return dict(user_is_admin=is_admin, user_perms=perms, nav_items=nav_items)

    @app.context_processor
    def inject_custom_themes_for_js():
        from .core.db_class.custom_theme import CustomTheme as CT
        from flask_login import current_user
        themes = []
        try:
            q = CT.query.filter_by(is_active=True, is_builtin=False)
            if not (current_user.is_authenticated and current_user.is_admin()):
                q = q.filter_by(is_public=True)
            for t in q.all():
                bg_body = (t.css_vars or {}).get('--bg-body', '')
                themes.append({'css_key': t.css_key, 'is_dark': t.is_dark, 'bg_body': bg_body})
        except Exception:
            pass
        return dict(custom_themes_for_js=themes)

    @app.context_processor
    def inject_app_version():
        import os
        version_path = os.path.join(app.root_path, '..', 'version')
        try:
            with open(version_path) as f:
                version = f.read().strip()
        except OSError:
            version = '0.0.0'
        return dict(app_version=version)

    with app.app_context():
        from .core.db_class.site_config import seed_site_config
        try:
            seed_site_config()
        except Exception:
            pass  # DB not yet created (first migration)

    from .core.utils.job_runner import init_runner
    init_runner(app)

    @app.before_request
    def update_last_seen():
        from flask_login import current_user
        from datetime import timedelta
        if current_user.is_authenticated:
            now = datetime.utcnow()
            if (current_user.last_seen_at is None or
                    now - current_user.last_seen_at > timedelta(minutes=2)):
                current_user.last_seen_at = now
                db.session.commit()

    return app
    
