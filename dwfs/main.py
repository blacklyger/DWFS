from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from . import db
from .models import User, Subjects, Media
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from functools import namedtuple
from os import mkdir, remove, listdir, path
from werkzeug.utils import secure_filename
from random import choice
from string import digits, ascii_letters
from shutil import rmtree
from pathlib import Path

main = Blueprint('main', __name__)

abs_path = Path("C:/Users/Simon/Desktop/XTEC/computer_science/software/DWFS/dwfs/static/upload")
chars = digits + ascii_letters

ALLOWED_EXTENSIONS = [
    "txt", "pdf", "zip", "tar",
    "docx", "mp3", "mp4", "pptx",
    "wav", "doc", "odp", "xls",
    "xlsx", "ppt", "pptm", "ott",
    "ods", "html", "JPG", "jpg",
    "jpeg"
]

def calculate_amount_of_media(subject):
    return len(Media.query.filter_by(name=current_user.username).filter_by(subject=subject).all())


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", username=current_user.username)


@main.route("/subjects")
@login_required
def subjects():
    _subject = namedtuple("subject", ["media", "access"])
    all_subject_names = [sub.subject for sub in Subjects.query.filter_by(name=current_user.username).all()]
    subject_names     = [(subj, len(Media.query.filter_by(subject=subj).filter_by(name=current_user.username).all())) for subj in reversed(all_subject_names)]

    if not all_subject_names:
        flash("Keine Fächer gefunden!", 'error')

    return render_template(
        "subjects.html",
        subject_names=subject_names
    )


def calc_file_size(filename, subject):
    file_path = Path(abs_path, f"{current_user.username}/{subject}/{filename}")
    if file_path.exists():
        return f"{file_path.stat().st_size / 1e+6:0.2f}"

    return None


@main.route("/edit_subject/<subject>")
@login_required
def edit_subject(subject):

    filtered_subjects = [sub.subject for sub in Subjects.query.filter_by(name=current_user.username).all()]

    if subject not in filtered_subjects:
        flash(f"Das Fach \"{subject}\" existiert nicht!", "error")
        return redirect(url_for('main.subjects'))

    d = Media.query.filter_by(name=current_user.username).filter_by(subject=subject).all()
    data = [(i + 1, f.filename, calc_file_size(f.filename, subject), f.unique_id) for i, f in enumerate(d)]

    if not data:
        flash("Es wurden keine Medien gefunden.", 'media_error')
    

    return render_template("edit_subject.html", subject=subject, data=data)


@login_required
@main.route("/add_media", methods=['POST'])
def add_media():
    files = request.files.getlist('media')
    current_subject = request.form.get('current_subject')

    if not files:
        flash("Bitte wählen Sie mindestens eine Datei aus.", 'error')
        return redirect(url_for('main.edit_subject', subject=current_subject))
    
    all_filenames  = [secure_filename(f.filename) for f in files]

    existing_media = [secure_filename(f.filename)       for f        in Media.query.filter_by(name=current_user.username).filter_by(subject=current_subject).all()]
    existing_files = [filename         for filename in existing_media if filename in all_filenames]
    all_uids       = [obj.unique_id    for obj      in Media.query.filter_by(name=current_user.username).all()]

    if existing_files:
        flash(f"Die Datei/en mit dem/n Namen \"{', '.join(existing_files)}\" existier/t/en bereits", 'error')
        return redirect(url_for('main.edit_subject', subject=current_subject))

    for filename in all_filenames:
        uid = ''.join(choice(chars) for i in range(10))
        if uid in all_uids:
            continue
        new_media_object = Media(current_user.username, current_subject, filename, uid)
        db.session.add(new_media_object)
    db.session.commit()

    file_path  = Path(abs_path, f"{current_user.username}/{current_subject}")

    for file in files:
        if file and allowed_file(file.filename):
            fname = file.filename
            filename = secure_filename(fname)
            file.save(path.join(file_path, filename))

    flash(f"Folgende Datei/en wurde/n erfolgreich hochgeladen und gespeichert: \"{', '.join(all_filenames)}\"", 'upload_success')

    return redirect(url_for('main.edit_subject', subject=current_subject))

@login_required
@main.route("/remove_media", methods=['POST'])
def remove_media():
    to_remove = request.form.getlist('media_to_remove')
    current_subject = request.form.get('current_subject')

    if not to_remove:
        flash("Bitte wählen Sie mindestens eine Datei aus.", 'error')
        return redirect(url_for('main.edit_subject', subject=current_subject))

    db_media = [f.filename for f in Media.query.filter_by(name=current_user.username).all() if f.filename in to_remove]
    
    for media_object in db_media:
        Media.query.filter_by(filename=media_object).filter_by(name=current_user.username).delete()
    db.session.commit()

    file_path  = Path(abs_path, f"{current_user.username}/{current_subject}")

    for file in db_media:
        Path(file_path, file).unlink()

    flash(f"Folgende Medien wurden erfolgreich gelöscht: \"{', '.join(to_remove)}\"", 'media_success')

    return redirect(url_for('main.edit_subject', subject=current_subject))


@main.route("/download/<uid>")
def download_file(uid):
    filtered_uid = Media.query.filter_by(unique_id=uid).first()

    if not filtered_uid:
        return redirect("https://origin7.de")

    file_path  = Path(abs_path, f"{filtered_uid.name}/{filtered_uid.subject}/{secure_filename(filtered_uid.filename)}")
    return send_file(file_path, as_attachment=True)


@main.route("/change_password", methods=['POST'])
@login_required
def change_password():
    password = request.form.get('password')
    password_confirm = request.form.get('password_confirm')

    if not password or not password_confirm:
        flash("Bitte füllen Sie die Felder aus.", 'error')
        return redirect(url_for('main.profile'))

    if password != password_confirm:
        flash("Die Passwörter stimmen nicht überein.", 'error')
        return redirect(url_for('main.profile'))

    user = User.query.filter_by(username=current_user.username).first()

    hashed_password = generate_password_hash(password, method='sha256')
    user.password = hashed_password
    db.session.commit()

    flash("Das Passwort wurde erfolgreich geändert.", 'success')

    return redirect(url_for('main.profile'))

@main.route("/add_subject", methods=['POST'])
def add_subject():

    subject = request.form.get('subject_name')

    if not subject:
        flash("Bitte füllen Sie das Feld aus!", "error")
        return redirect(url_for('main.subjects'))

    filtered_subjects = [subj.subject for subj in Subjects.query.filter_by(subject=subject).all()]

    if filtered_subjects:
        flash(f"Das Fach \"{subject}\" existiert bereits!", "error")
        return redirect(url_for('main.subjects'))

    new_subject = Subjects(current_user.username, subject)
    db.session.add(new_subject)
    db.session.commit()

    try:
        mkdir(Path(abs_path, f"{current_user.username}"))
    except FileExistsError:
        pass

    mkdir(Path(abs_path, f"{current_user.username}/{subject}"))

    return redirect(url_for('main.subjects'))

@main.route("/remove_subject", methods=['POST'])
def remove_subject():
    subject_s = request.form.getlist('subject_to_remove')
    
    for subject in subject_s:
        subj_mod  = Subjects.query.filter_by(name=current_user.username).filter_by(subject=subject).delete()
        media_mod = Media.query.filter_by(name=current_user.username).filter_by(subject=subject).delete()

        file_path = Path(abs_path, f"{current_user.username}/{subject}")
        rmtree(file_path)

    return redirect(url_for('main.subjects'))

@main.route("/add_subject_dev", methods=['POST'])
def add_subject_dev():

    t_name = request.form.get('username')
    subject = request.form.get('subject')

    new_sub = Subjects(t_name, subject)
    db.session.add(new_sub)
    db.session.commit()

    try:
        mkdir(Path(abs_path, f"{t_name}"))
    except FileExistsError:
        pass

    mkdir(Path(abs_path, f"{t_name}/{subject}"))

    return redirect(url_for('main.profile'))
