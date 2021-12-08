from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

db = SQLAlchemy()
csrf = CSRFProtect()

app = Flask(__name__)

app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = 'REMOVED'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

db.init_app(app)
csrf.init_app(app)

@app.before_first_request
def create_tables():
    db.create_all()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Bitte melden Sie sich zuerst an!"
login_manager.init_app(app)

from .models import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.context_processor
def secure_fname():
    def get_secure_filename(fname):
        return secure_filename(fname)
    return dict(get_secure_filename=get_secure_filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0")