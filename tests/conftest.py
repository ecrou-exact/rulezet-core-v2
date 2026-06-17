import sys
import os
sys.path.append(os.getcwd())
from app import create_app, db
from app.core.utils.init_db import create_user_test
import pytest

# App is created once per session to avoid SQLAlchemy MetaData conflicts
# (flask_session re-registers its table on every create_app() call).
@pytest.fixture(scope="session")
def app():
    os.environ.setdefault("FLASKENV", "testing")
    _app = create_app()
    _app.config.update({
        "TESTING": True,
        "SERVER_NAME": f"{_app.config.get('FLASK_URL')}:{_app.config.get('FLASK_PORT')}"
    })
    yield _app


# DB is reset per test for full isolation.
@pytest.fixture
def client(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        create_user_test()
    with app.test_client() as c:
        yield c
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()