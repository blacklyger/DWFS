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

main = Blueprint('main', __name__)

abs_path = "/home/lyger/dwfs/dwfs/static/upload"
chars = digits + ascii_letters

all_subjects = [
    "Mathematik",  "Deutsch",    "Englisch",
    "Französisch", "Spanisch",   "Latein",
    "Physik",      "Chemie",     "Biologie", 
    "Kunst",       "Geschichte", "Erdkunde", 
    "Politik",     "Sport"
]

ALLOWED_EXTENSIONS = [
    "txt", "pdf", "zip", "tar",
    "docx", "mp3", "mp4", "pptx",
    "wav", "doc", "odp", "xls",
    "xlsx", "ppt", "pptm", "ott",
    "ods", "html",
]

def calculate_amount_of_media(subject):
    return len(Media.query.filter_by(teacher_name=current_user.username).filter_by(subject=subject).all())


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", username=current_user.username, role=current_user.role)


@main.route("/subjects")
@login_required
def subjects():
    _subject = namedtuple("subject", ["media", "access"])
    all_subject_names = [sub.subject for sub in Subjects.query.filter_by(teacher_name=current_user.username).all()]

    if not all_subject_names:
        flash("Sie haben (noch) keinen Zugang zu Fächern", 'error')


    mathematik  = _subject(calculate_amount_of_media("Mathematik"),  "Ja" if 'Mathematik'   in all_subject_names else "Nein")
    deutsch     = _subject(calculate_amount_of_media("Deutsch"),     "Ja" if 'Deutsch'      in all_subject_names else "Nein")
    englisch    = _subject(calculate_amount_of_media("Englisch"),    "Ja" if 'Englisch'     in all_subject_names else "Nein")
    französisch = _subject(calculate_amount_of_media("Französisch"), "Ja" if 'Französisch'  in all_subject_names else "Nein")
    spanisch    = _subject(calculate_amount_of_media("Spanisch"),    "Ja" if 'Spanisch'     in all_subject_names else "Nein")
    latein      = _subject(calculate_amount_of_media("Latein"),      "Ja" if 'Latein'       in all_subject_names else "Nein")
    physik      = _subject(calculate_amount_of_media("Physik"),      "Ja" if 'Physik'       in all_subject_names else "Nein")
    chemie      = _subject(calculate_amount_of_media("Chemie"),      "Ja" if 'Chemie'       in all_subject_names else "Nein")
    biologie    = _subject(calculate_amount_of_media("Biologie"),    "Ja" if 'Biologie'     in all_subject_names else "Nein")
    kunst       = _subject(calculate_amount_of_media("Kunst"),       "Ja" if 'Kunst'        in all_subject_names else "Nein")
    geschichte  = _subject(calculate_amount_of_media("Geschichte"),  "Ja" if 'Geschichte'   in all_subject_names else "Nein")
    erdkunde    = _subject(calculate_amount_of_media("Erdkunde"),    "Ja" if 'Erdkunde'     in all_subject_names else "Nein")
    politik     = _subject(calculate_amount_of_media("Politik"),     "Ja" if 'Politik'      in all_subject_names else "Nein")
    sport       = _subject(calculate_amount_of_media("Sport"),       "Ja" if 'Sport'        in all_subject_names else "Nein")

    return render_template(
        "subjects.html",
        mathematik=mathematik,
        deutsch=deutsch,
        englisch=englisch,
        französisch=französisch,
        spanisch=spanisch,
        latein=latein,
        physik=physik,
        chemie=chemie,
        biologie=biologie,
        kunst=kunst,
        geschichte=geschichte,
        erdkunde=erdkunde,
        politik=politik,
        sport=sport
    )


@login_required
@main.route("/edit_subject/<subject>")
def edit_subject(subject):
    if subject not in all_subjects:
        flash(f"Das Fach \"{subject}\" existiert nicht.", 'error')
        return redirect(url_for('main.subjects'))

    d = Media.query.filter_by(teacher_name=current_user.username).filter_by(subject=subject).all()
    data = [(i + 1, f.filename, f.unique_id) for i, f in enumerate(d)]

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
    
    all_filenames  = [f.filename       for f        in files]
    existing_media = [f.filename       for f        in Media.query.filter_by(teacher_name=current_user.username).filter_by(subject=current_subject).all()]
    existing_files = [filename         for filename in existing_media if filename in all_filenames]
    all_uids       = [obj.unique_id    for obj      in Media.query.filter_by(teacher_name=current_user.username).all()]

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

    file_path = path.join(abs_path, f"{current_user.username}\\{current_subject}")

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
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

    db_media = [f.filename for f in Media.query.filter_by(teacher_name=current_user.username).all() if f.filename in to_remove]
    
    for media_object in db_media:
        Media.query.filter_by(filename=media_object).filter_by(teacher_name=current_user.username).delete()
    db.session.commit()

    file_path = path.join(abs_path, f"{current_user.username}\\{current_subject}")

    for file in db_media:
        remove(path.join(file_path, file))

    flash(f"Folgende Medien wurden erfolgreich gelöscht: \"{', '.join(to_remove)}\"", 'media_success')

    return redirect(url_for('main.edit_subject', subject=current_subject))


@main.route("/download/<uid>")
def download_file(uid):
    filtered_uid = Media.query.filter_by(unique_id=uid).first()

    if not filtered_uid:
        return redirect(url_for('main.index'))

    file_path = path.join(abs_path, f"{filtered_uid.teacher_name}\\{filtered_uid.subject}\\{filtered_uid.filename}")
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

@login_required
@main.route("/add_subject", methods=['POST'])
def add_subject():

    t_name = request.form.get('username')
    subject = request.form.get('subject')

    new_sub = Subjects(t_name, subject)
    db.session.add(new_sub)
    db.session.commit()

    try:
        mkdir(path.join(abs_path, f"{t_name}"))
    except FileExistsError:
        pass

    mkdir(path.join(abs_path, f"{t_name}\\{subject}"))

    return redirect(url_for('main.profile'))