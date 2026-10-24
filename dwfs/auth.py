from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, abort
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from .security import valid_username, valid_password, login_throttle, MIN_PASSWORD_LENGTH
from flask_login import login_user, login_required, logout_user, current_user

auth = Blueprint('auth', __name__)

ROLES = ("User", "Admin")

# Hash used to keep the login timing identical for unknown usernames.
DUMMY_HASH = generate_password_hash("dwfs-timing-dummy", method="scrypt")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@auth.route('/login')
def login():
    return render_template('login.html')


@auth.route('/login', methods=['POST'])
def login_some():
    username = request.form.get('username', '')
    password = request.form.get('password', '')

    if login_throttle.is_blocked(username):
        flash("Zu viele fehlgeschlagene Versuche. Bitte warten Sie 15 Minuten.")
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(username=username).first()
    password_ok = check_password_hash(user.password if user else DUMMY_HASH, password)

    if not user or not password_ok:
        login_throttle.fail(username)
        flash("Bitte überprüfen Sie ihre Eingabe!")
        return redirect(url_for('auth.login'))

    login_throttle.reset(username)
    session.clear()
    login_user(user)
    return redirect(url_for('main.profile'))


@auth.route('/register')
@admin_required
def register():
    return render_template('register.html')

@auth.route('/register', methods=['POST'])
@admin_required
def register_some():
    username = request.form.get('username')
    password = request.form.get('password')
    role     = request.form.get('selector')

    if not valid_username(username):
        flash("Ungültiger Nutzername (3-32 Zeichen: Buchstaben, Ziffern, '_' und '-').")
        return redirect(url_for('auth.register'))

    if not valid_password(password):
        flash(f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.")
        return redirect(url_for('auth.register'))

    if role not in ROLES:
        flash("Ungültige Rolle.")
        return redirect(url_for('auth.register'))

    user = User.query.filter_by(username=username).first()

    if user:
        flash(f"Der Nutzer \"{username}\" existiert bereits!")
        return redirect(url_for('auth.register'))

    new_user = User(username=username, password=generate_password_hash(password, method='scrypt'), role=role)

    db.session.add(new_user)
    db.session.commit()

    flash(f"Der Nutzer \"{username}\" wurde angelegt.")
    return redirect(url_for('auth.register'))

@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('main.index'))
