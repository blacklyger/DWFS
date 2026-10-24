import os
from collections import namedtuple
from datetime import datetime
from math import ceil
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, abort
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash

from . import db
from .auth import admin_required
from .models import User, Subjects, Media, AccountRequest
from .security import (
    PathViolation, clean_name, confine, data_dir, generate_uid, is_clean_segment,
    safe_redirect_target, segments_from_url, user_subject_path, valid_password,
    valid_username, MIN_PASSWORD_LENGTH,
)

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {
    "txt", "pdf", "zip", "tar",
    "docx", "mp3", "mp4", "pptx",
    "wav", "doc", "odp", "xls",
    "xlsx", "ppt", "pptm", "ott",
    "ods", "html", "jpg",
    "jpeg", "tex", "opus", "png",
    "mkv"
}

# Only these types are rendered in the browser. Everything else (notably HTML)
# is forced to download, so uploaded files can never execute script on our origin.
INLINE_EXTENSIONS = {"pdf", "txt", "png", "jpg", "jpeg", "mp3", "mp4", "wav", "opus", "mkv"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ""


def owned_subject(subject):
    if not is_clean_segment(subject):
        return None
    return Subjects.query.filter_by(name=current_user.username, subject=subject).first()


def require_subject(subject):
    if not owned_subject(subject):
        abort(404)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/request_account")
def request_account():
    return render_template("request_account.html")


def parse_file_path(url, subject):
    """
    Map the client supplied page URL to the matching directory of the current
    user. Every segment is validated and the result is confined to DATA_DIR.
    """
    require_subject(subject)
    return str(user_subject_path(current_user.username, subject, *segments_from_url(url, subject)))


@main.route("/regenerate_uids", methods=["POST"])
@login_required
def regenerate_uids():

    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("current_path")
    to_change        = request.form.getlist('change[]')
    parsed_file_path = parse_file_path(current_path, current_subject)
    all_uids         = {obj.unique_id for obj in Media.query.with_entities(Media.unique_id)}

    for file in to_change:

        media_obj = Media.query.filter_by(name=current_user.username, subject=current_subject, path=parsed_file_path, filename=file).first()

        if not media_obj:
            continue

        new_uid = generate_uid(all_uids)
        all_uids.add(new_uid)

        if media_obj.is_dir():
            for file_in_folder in Media.query.filter_by(name=current_user.username, in_folder=media_obj.unique_id).all():
                if not file_in_folder.is_dir():
                    file_in_folder.in_folder = new_uid
            media_obj.unique_id = new_uid
        else:
            media_obj.unique_id = f"{media_obj.filename.rsplit('.', 1)[0]}_{new_uid}"

    db.session.commit()

    return "true"

@main.route("/req_new_acc", methods=["POST"])
def req_new_acc():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        flash("Bitte füllen Sie die Felder aus!", 'error')
        return redirect(url_for("main.request_account"))

    if not valid_username(username):
        flash("Ungültiger Nutzername (3-32 Zeichen: Buchstaben, Ziffern, '_' und '-').", 'error')
        return redirect(url_for("main.request_account"))

    if not valid_password(password):
        flash(f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.", 'error')
        return redirect(url_for("main.request_account"))

    if AccountRequest.query.filter_by(username=username).first() or User.query.filter_by(username=username).first():
        flash(f"Der Nutzer \"{username}\" existiert bereits!", 'error')
        return redirect(url_for("main.request_account"))

    user_request = AccountRequest(
        username  =username,
        password  =generate_password_hash(password, method="scrypt"),
        date      =datetime.now(),
        ip_address=request.remote_addr
    )

    db.session.add(user_request)
    db.session.commit()

    flash("Ihre Anfrage wurde gesendet und wird von einem Admin geprüft.", 'success')
    return redirect(url_for("main.request_account"))


@main.route("/show_account_requests")
@admin_required
def show_account_requests():

    requests = AccountRequest.query.all()
    requests = [
        (
            obj.id,
            obj.username,
            obj.date.strftime("%d.%m.%y %H:%M"),
            obj.ip_address
        )

        for obj in requests
    ]

    return render_template("show_account_requests.html", requests=requests)


@main.route("/create_request_account", methods=["POST"])
@admin_required
def create_request_account():

    request_split = namedtuple("req_split", "state user")
    requests      = request.form.getlist("access")

    for req in requests:
        parts = req.split()
        if len(parts) != 2:
            continue

        to_check = request_split(*parts)
        if to_check.state != "yes":
            continue

        account_request = AccountRequest.query.filter_by(username=to_check.user).first()
        if not account_request or User.query.filter_by(username=account_request.username).first():
            continue

        # The request already holds a password hash, it is copied over as is.
        db.session.add(User(account_request.username, account_request.password, "User"))
        db.session.delete(account_request)

    db.session.commit()

    return redirect(url_for("main.show_account_requests"))


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", username=current_user.username)


@main.route("/subjects")
@login_required
def subjects():

    all_subject_names = [sub.subject for sub in Subjects.query.filter_by(name=current_user.username).all()]
    subject_names     = [(subj, Media.query.filter_by(subject=subj, name=current_user.username).count()) for subj in reversed(all_subject_names)]

    if not all_subject_names:
        flash("Keine Fächer gefunden.", 'error')

    return render_template(
        "subjects.html",
        subject_names=subject_names
    )


def calc_file_size(path, filename):

    file_path = Path(path, filename)
    if file_path.is_file():
        return f"{file_path.stat().st_size / 1e+6:0.2f}"

    return None


def create_url_from_media_path(media_path: str, filename: str) -> str:

    parts = Path(media_path).relative_to(Path(data_dir(), current_user.username)).parts
    return url_for("main.edit_subject", subject=parts[0], p="/".join(parts[1:] + (filename,)))


@main.route("/edit_subject/<subject>", defaults={"p": None})
@main.route("/edit_subject/<subject>/<path:p>")
@login_required
def edit_subject(subject, p):

    page = request.args.get("page", "1")
    limit = request.args.get("limit", "10")

    page = int(page) if page.isdigit() and int(page) > 0 else 1
    limit = min(int(limit), 100) if limit.isdigit() and int(limit) > 0 else 10

    if not owned_subject(subject):
        flash(f"Das Fach \"{subject}\" existiert nicht!", "error")
        return redirect(url_for('main.subjects'))

    segments = p.split("/") if p else []
    path = user_subject_path(current_user.username, subject, *segments)

    root_data = Media.query.filter_by(
        name=current_user.username,
        subject=subject,
        path=str(path)
    )

    data = [
        (
            i + 1,
            f.filename,
            calc_file_size(f.path, f.filename),
            f.is_dir(),
            create_url_from_media_path(f.path, f.filename),
            f.unique_id
        )

        for i, f in enumerate(reversed(root_data.offset((page - 1) * limit).limit(limit).all()))
    ]

    if not data:
        flash("Es wurden keine Medien gefunden.", 'media_error')

    return render_template(
        "edit_subject.html",
        subject=subject,
        data=data,
        num_pages=ceil(root_data.count() / limit),
        current_page=page,
        current_limit=limit
    )


def get_folder_uid(subject, segments):

    """
    Determine the folder_uid of the folder where an uploaded file is in.
    """

    if not segments:
        return "root"

    parent_path = user_subject_path(current_user.username, subject, *segments[:-1])
    folder = Media.query.filter_by(
        name=current_user.username, subject=subject, filename=segments[-1], path=str(parent_path), category="folder"
    ).first()

    if not folder:
        abort(404)

    return folder.unique_id

def add_media_data(
    files_to_upload,
    subject,
    username,
    disk_path,
    folder_uid
):
    """
    Store uploaded files in disk_path (which must already be confined to DATA_DIR)
    and register them in the database. Returns "OK" or an error message.
    """
    files_to_upload = [f for f in files_to_upload if f and f.filename]

    if not files_to_upload:
        return "Bitte wählen Sie mindestens eine Datei aus."

    target_dir = confine(Path(disk_path))
    if not target_dir.is_dir():
        return "Der Zielordner existiert nicht."

    accepted, rejected = [], []
    for f in files_to_upload:
        filename = clean_name(f.filename)
        if filename and allowed_file(filename) and filename not in [a[0] for a in accepted]:
            accepted.append((filename, f))
        else:
            rejected.append(f.filename)

    existing_media = {m.filename for m in Media.query.filter_by(name=username, subject=subject, path=str(target_dir))}
    existing_files = [filename for filename, _ in accepted if filename in existing_media]

    if existing_files:
        return f"""Die Datei/en mit dem/n Namen \"{', '.join(existing_files)}\" existier/t/en bereits"""

    all_uids = {obj.unique_id for obj in Media.query.with_entities(Media.unique_id)}

    for filename, f in accepted:
        uid = generate_uid(all_uids)
        all_uids.add(uid)

        f.save(confine(target_dir, filename))

        db.session.add(Media(
            name     =username,
            subject  =subject,
            filename =filename,
            path     =str(target_dir),
            category ="file",
            unique_id=f"{filename.rsplit('.', 1)[0]}_{uid}",
            in_folder=folder_uid,
            faccess=True
        ))
    db.session.commit()

    if rejected:
        return f"Nicht erlaubte Dateien wurden übersprungen: {', '.join(rejected)}"

    return "OK"

@main.route("/add_media", methods=['POST'])
@login_required
def add_media():
    current_subject  = request.form.get('current_subject')
    file_path_url    = request.form.get("file_path")
    parsed_file_path = parse_file_path(file_path_url, current_subject)
    folder_uid       = get_folder_uid(current_subject, segments_from_url(file_path_url, current_subject))

    return add_media_data(
        files_to_upload=list(request.files.values()),
        subject=current_subject,
        username=current_user.username,
        disk_path=parsed_file_path,
        folder_uid=folder_uid
    )

def media_below(username, folder_path):
    """All media of a user located in folder_path or any of its subfolders."""
    return Media.query.filter_by(name=username).filter(or_(
        Media.path == folder_path,
        Media.path.startswith(folder_path + "/", autoescape=True)
    ))

@main.route("/remove_media", methods=['POST'])
@login_required
def remove_media():

    to_remove        = request.form.getlist('media_to_remove')
    current_subject  = request.form.get('current_subject')
    current_path     = request.form.get("current_path")
    parsed_file_path = parse_file_path(current_path, current_subject)
    redirect_target  = safe_redirect_target(current_path, url_for('main.edit_subject', subject=current_subject))

    if not to_remove:
        flash("Bitte wählen Sie mindestens eine Datei aus.", 'error')
        return redirect(redirect_target)

    db_media = Media.query.filter_by(name=current_user.username, subject=current_subject, path=parsed_file_path).filter(
        Media.filename.in_(to_remove)
    ).all()

    for media_object in db_media:
        disk_path = confine(Path(parsed_file_path, media_object.filename))

        if media_object.is_dir():
            media_below(current_user.username, str(disk_path)).delete(synchronize_session=False)
            rmtree(disk_path, ignore_errors=True)
        else:
            disk_path.unlink(missing_ok=True)

        db.session.delete(media_object)

    db.session.commit()

    flash(f"Folgende Medien wurden erfolgreich gelöscht: \"{', '.join(m.filename for m in db_media)}\"", 'media_success')

    return redirect(redirect_target)


@main.route("/download/<uid>")
def download_file(uid):
    """
    Public download via an unguessable share link (the uid). HTML and other
    active content is always served as attachment.
    """
    media_obj = Media.query.filter_by(unique_id=uid, category="file").first()

    if not media_obj:
        abort(404)

    try:
        file_path = confine(media_obj.path, media_obj.filename)
    except PathViolation:
        abort(404)

    if not file_path.is_file():
        abort(404)

    return send_file(
        file_path,
        as_attachment=file_extension(media_obj.filename) not in INLINE_EXTENSIONS,
        download_name=media_obj.filename,
    )

@main.route("/download_files", methods=['POST'])
@login_required
def download_files():
    """Bundle the selected files and folders (recursively) into a ZIP archive."""
    current_subject   = request.form.get('current_subject')
    current_path      = request.form.get("current_path")
    files_to_download = request.form.getlist("change[]")
    parsed_file_path  = parse_file_path(current_path, current_subject)

    media = Media.query.filter_by(name=current_user.username, subject=current_subject, path=parsed_file_path).filter(
        Media.filename.in_(files_to_download)
    ).all()

    if not media:
        abort(400)

    archive = TemporaryFile()

    with ZipFile(archive, "w", ZIP_DEFLATED) as zf:
        for media_obj in media:
            disk_path = confine(Path(parsed_file_path, media_obj.filename))

            if not media_obj.is_dir():
                if disk_path.is_file():
                    zf.write(disk_path, media_obj.filename)
                continue

            for root, _, files in os.walk(disk_path, followlinks=False):
                for name in files:
                    file_path = Path(root, name)
                    if not file_path.is_symlink():
                        zf.write(file_path, file_path.relative_to(parsed_file_path))

    archive.seek(0)
    return send_file(archive, mimetype="application/zip", as_attachment=True, download_name=f"{current_subject}.zip")


@main.route("/change_password", methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    password = request.form.get('password')
    password_confirm = request.form.get('password_confirm')

    if not current_password or not password or not password_confirm:
        flash("Bitte füllen Sie die Felder aus.", 'error')
        return redirect(url_for('main.profile'))

    if not check_password_hash(current_user.password, current_password):
        flash("Das aktuelle Passwort ist falsch.", 'error')
        return redirect(url_for('main.profile'))

    if password != password_confirm:
        flash("Die Passwörter stimmen nicht überein.", 'error')
        return redirect(url_for('main.profile'))

    if not valid_password(password):
        flash(f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.", 'error')
        return redirect(url_for('main.profile'))

    current_user.password = generate_password_hash(password, method='scrypt')
    db.session.commit()

    flash("Das Passwort wurde erfolgreich geändert.", 'success')

    return redirect(url_for('main.profile'))


def create_subject(username, subject):
    if Subjects.query.filter_by(name=username, subject=subject).first():
        return False

    user_subject_path(username, subject).mkdir(parents=True, exist_ok=True)
    db.session.add(Subjects(username, subject))
    db.session.commit()
    return True

@main.route("/add_subject", methods=['POST'])
@login_required
def add_subject():

    subject = clean_name(request.form.get('subject_name'))

    if not subject:
        flash("Bitte füllen Sie das Feld aus!", "error")
        return redirect(url_for('main.subjects'))

    if not create_subject(current_user.username, subject):
        flash(f"Das Fach \"{subject}\" existiert bereits!", "error")

    return redirect(url_for('main.subjects'))

@main.route("/remove_subject", methods=['POST'])
@login_required
def remove_subject():

    for subject in request.form.getlist('subject_to_remove'):
        if not owned_subject(subject):
            continue

        Subjects.query.filter_by(name=current_user.username, subject=subject).delete()
        Media.query.filter_by(name=current_user.username, subject=subject).delete()
        rmtree(user_subject_path(current_user.username, subject), ignore_errors=True)

    db.session.commit()

    return redirect(url_for('main.subjects'))


def move_media_paths(username, old_dir: Path, new_dir: Path):
    """Rewrite the stored paths of everything below old_dir after a rename."""
    for media_obj in media_below(username, str(old_dir)).all():
        media_obj.path = str(new_dir / Path(media_obj.path).relative_to(old_dir))


@main.route("/rename_subject", methods=["POST"])
@login_required
def rename_subject():
    old_subject_name = request.form.get("old_subject_name")
    new_subject_name = clean_name(request.form.get("new_subject_name"))

    subjects_match = owned_subject(old_subject_name)

    if not subjects_match:
        flash(f"Das Fach \"{old_subject_name}\" existiert nicht!", 'error')
        return redirect(url_for('main.subjects'))

    if not new_subject_name or owned_subject(new_subject_name):
        flash(f"Das Fach \"{new_subject_name}\" existiert bereits oder ist ungültig!", 'error')
        return redirect(url_for('main.subjects'))

    old_dir = user_subject_path(current_user.username, old_subject_name)
    new_dir = user_subject_path(current_user.username, new_subject_name)

    move_media_paths(current_user.username, old_dir, new_dir)
    Media.query.filter_by(name=current_user.username, subject=old_subject_name).update({"subject": new_subject_name})
    subjects_match.subject = new_subject_name

    old_dir.rename(new_dir)
    db.session.commit()

    return redirect(url_for("main.subjects"))


@main.route("/rename_file", methods=["POST"])
@login_required
def rename_file():
    old_filename     = request.form.get("old_filename")
    new_filename     = clean_name(request.form.get("new_filename"))
    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("rename_path")
    parsed_file_path = parse_file_path(current_path, current_subject)
    redirect_target  = safe_redirect_target(current_path, url_for('main.edit_subject', subject=current_subject))

    match = Media.query.filter_by(
        name=current_user.username,
        subject=current_subject,
        filename=old_filename,
        path=parsed_file_path
    ).first()

    if not match:
        flash(f"Die Datei bzw. der Ordner mit dem Namen \"{old_filename}\" existiert nicht!", 'error')
        return redirect(redirect_target)

    if not new_filename or Media.query.filter_by(name=current_user.username, path=parsed_file_path, filename=new_filename).first():
        flash(f"Der Name \"{new_filename}\" ist ungültig oder existiert bereits!", 'error')
        return redirect(redirect_target)

    old_disk_path = confine(Path(parsed_file_path, old_filename))
    new_disk_path = confine(Path(parsed_file_path, new_filename))

    if match.is_dir():
        move_media_paths(current_user.username, old_disk_path, new_disk_path)
    else:
        if file_extension(old_filename) != file_extension(new_filename):
            flash("Die Dateiendungen stimmen nicht überein!", 'error')
            return redirect(redirect_target)

        match.unique_id = f"{new_filename.rsplit('.', 1)[0]}_{match.unique_id.rsplit('_', 1)[-1]}"

    match.filename = new_filename
    old_disk_path.rename(new_disk_path)
    db.session.commit()

    return redirect(redirect_target)

@main.route("/add_subject_dev", methods=['POST'])
@admin_required
def add_subject_dev():

    t_name = request.form.get('username')
    subject = clean_name(request.form.get('subject'))

    if not subject or not User.query.filter_by(username=t_name).first():
        flash("Unbekannter Nutzer oder ungültiges Fach.")
        return redirect(url_for('auth.register'))

    if not create_subject(t_name, subject):
        flash(f"Das Fach \"{subject}\" existiert bereits!")
        return redirect(url_for('auth.register'))

    flash(f"Das Fach \"{subject}\" wurde für \"{t_name}\" angelegt.")
    return redirect(url_for('auth.register'))
