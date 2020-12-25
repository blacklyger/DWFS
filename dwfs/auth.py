from flask import Blueprint, render_template, redirect, url_for, request, flash
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from flask_login import login_user, login_required, logout_user, current_user

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return render_template('login.html')


@auth.route('/login', methods=['POST'])
def login_some():
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        flash("Bitte überprüfen Sie ihre Eingabe!")
        return redirect(url_for('auth.login'))

    login_user(user)
    return redirect(url_for('main.profile'))


@auth.route('/register')
def register():
    return render_template('register.html')


@auth.route('/register', methods=['POST'])
def register_some():
    username = request.form.get('username')
    password = request.form.get('password')
    subject = request.form.get('subject')
    role    = request.form.get('selector')

    user = User.query.filter_by(username=username).first()

    if user:
        flash(f"Der Admin \"{username}\" existiert bereits!")
        return redirect(url_for('auth.register'))

    new_user = User(username=username, password=generate_password_hash(password, method='sha256'), role=role)

    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))