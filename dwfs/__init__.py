import os
import secrets
from pathlib import Path

import click
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

db = SQLAlchemy()
csrf = CSRFProtect()

app = Flask(__name__, instance_relative_config=True)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)


def env_flag(name, default):
    return os.environ.get(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def load_secret_key():
    """
    Use DWFS_SECRET_KEY if set, otherwise generate a random key once and
    persist it (mode 0600) in the instance folder. Never hardcode it.
    """
    if os.environ.get("DWFS_SECRET_KEY"):
        return os.environ["DWFS_SECRET_KEY"]

    key_file = Path(app.instance_path, "secret_key")
    if not key_file.exists():
        # Write to a private temp file and link it into place atomically, so
        # concurrently starting worker processes all end up with the same key.
        tmp_file = key_file.with_name(f".secret_key.{os.getpid()}")
        fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
        try:
            os.link(tmp_file, key_file)
        except FileExistsError:
            pass
        finally:
            tmp_file.unlink()

    return key_file.read_text().strip()


app.url_map.strict_slashes = False
app.config["SECRET_KEY"] = load_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DWFS_DATABASE_URL", f"sqlite:///{Path(app.instance_path, 'dwfs.sqlite')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("DWFS_MAX_UPLOAD_MB", "2048")) * 1024 * 1024
app.config["DATA_DIR"] = Path(
    os.environ.get("DWFS_DATA_DIR", Path(app.root_path).parent / "data")
).resolve()
app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)

# Session cookie hardening. Set DWFS_COOKIE_SECURE=0 only for local HTTP testing.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = env_flag("DWFS_COOKIE_SECURE", True)
app.config["WTF_CSRF_TIME_LIMIT"] = None

# Only trust X-Forwarded-* headers when explicitly running behind a reverse proxy.
if env_flag("DWFS_BEHIND_PROXY", False):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)
csrf.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Bitte melden Sie sich zuerst an!"
login_manager.session_protection = "strong"
login_manager.init_app(app)

from .models import User


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()

from .auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint)

from .main import main as main_blueprint
app.register_blueprint(main_blueprint)

from .folder import folder as folder_blueprint
app.register_blueprint(folder_blueprint)

from .share import share as share_blueprint
app.register_blueprint(share_blueprint)

from .search import search as search_blueprint
app.register_blueprint(search_blueprint)

CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://code.jquery.com",
    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


from .security import PathViolation


@app.errorhandler(PathViolation)
def handle_path_violation(error):
    return "Ungültiger Pfad.", 400


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.context_processor
def secure_fname():
    def get_secure_filename(fname):
        return secure_filename(fname)
    return dict(get_secure_filename=get_secure_filename)


@app.cli.command("create-admin")
@click.argument("username")
@click.password_option()
def create_admin(username, password):
    """Create the initial admin account (registration is admin-only)."""
    from werkzeug.security import generate_password_hash
    from .security import valid_username, valid_password

    if not valid_username(username):
        raise click.BadParameter("3-32 Zeichen, nur Buchstaben, Ziffern, '_' und '-'.")
    if not valid_password(password):
        raise click.BadParameter("Das Passwort muss mindestens 10 Zeichen lang sein.")
    if User.query.filter_by(username=username).first():
        raise click.ClickException(f"Nutzer \"{username}\" existiert bereits.")

    db.session.add(User(username, generate_password_hash(password, method="scrypt"), "Admin"))
    db.session.commit()
    click.echo(f"Admin \"{username}\" wurde angelegt.")
