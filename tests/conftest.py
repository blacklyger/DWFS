import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# The app is configured at import time, so the environment is prepared first.
TMP = Path(tempfile.mkdtemp(prefix="dwfs-tests-"))
os.environ["DWFS_DATA_DIR"] = str(TMP / "data")
os.environ["DWFS_DATABASE_URL"] = f"sqlite:///{TMP / 'test.sqlite'}"
os.environ["DWFS_SECRET_KEY"] = "test-secret-key"
os.environ["DWFS_COOKIE_SECURE"] = "0"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from werkzeug.security import generate_password_hash  # noqa: E402

from dwfs import app as flask_app, db  # noqa: E402
from dwfs.models import User  # noqa: E402
from dwfs.security import login_throttle  # noqa: E402

PASSWORD = "correct-horse-battery"
CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    # No app context is held open during requests, otherwise Flask would reuse
    # it (and its `g`) for every request of the test client.
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    shutil.rmtree(flask_app.config["DATA_DIR"], ignore_errors=True)
    flask_app.config["DATA_DIR"].mkdir(parents=True)
    login_throttle._failures.clear()
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(username, role="User"):
    with flask_app.app_context():
        db.session.add(User(username, generate_password_hash(PASSWORD, method="scrypt"), role))
        db.session.commit()


def csrf_token(client, url="/login"):
    return CSRF_RE.search(client.get(url).get_data(as_text=True)).group(1)


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password, "csrf_token": csrf_token(client)})


@pytest.fixture
def user(client):
    """A logged-in user 'alice' with the subject 'Mathe'. Returns a helper object."""
    make_user("alice")
    login(client, "alice")

    class Session:
        token = csrf_token(client, "/subjects")
        base = "http://localhost/edit_subject/Mathe"

        def post(self, url, **data):
            data.setdefault("csrf_token", self.token)
            return client.post(url, data=data)

    s = Session()
    s.post("/add_subject", subject_name="Mathe")
    return s
