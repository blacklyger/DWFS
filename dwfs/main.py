from operator import add
from urllib import parse
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from . import db
from .models import User, Subjects, Media, AccountRequest
from flask_login import current_user, login_required, AnonymousUserMixin
from werkzeug.security import generate_password_hash
from functools import namedtuple
from os import mkdir, remove, listdir, path
from werkzeug.utils import secure_filename
from random import choice
from string import digits, ascii_letters
from shutil import rmtree, move
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from .share import share

main = Blueprint('main', __name__)

abs_path = Path("D:\\XTEC\\computer_science\\software\\DWFS\\dwfs\\data")
chars = digits + ascii_letters

nx = "\\"

ALLOWED_EXTENSIONS = [
    "txt", "pdf", "zip", "tar",
    "docx", "mp3", "mp4", "pptx",
    "wav", "doc", "odp", "xls",
    "xlsx", "ppt", "pptm", "ott",
    "ods", "html", "JPG", "jpg",
    "jpeg", "tex", "opus", "png",
    "mkv"
]

def calculate_amount_of_media(subject):
    return len(Media.query.filter_by(name=current_user.username).filter_by(subject=subject).all())


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route("/")
def index():
    return render_template("index.html")


@main.route("/request_account")
def request_account():
    return render_template("request_account.html")
    

def parse_file_path(url, subject):
    
    if url == url_for("main.edit_subject", subject=subject, _external=True):
        return str(Path(abs_path, f"{current_user.username}/{subject}"))

    parsed_url = urlparse(url)
    return str(Path(abs_path, f"{current_user.username}/{subject}/{'/'.join(parsed_url.path.rsplit('/')[3:])}"))


@main.route("/regenerate_uids", methods=["POST"])
def regenerate_uids():

    uidsplit         = namedtuple("uidsplit", "filename uid")
    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("current_path")
    to_change        = request.form.getlist('change[]')
    parsed_file_path = parse_file_path(current_path, current_subject)
  
    for file in to_change:

        media_obj = Media.query.filter_by(name=current_user.username).filter_by(subject=current_subject).filter_by(path=parsed_file_path).filter_by(filename=file).first()

        files_in_folder = []
        all_uids = [obj.unique_id for obj in Media.query.all()]
        new_uid  = ''.join(choice(chars) for i in range(10))

        if new_uid in all_uids:
            continue

        if media_obj.is_dir():
            files_in_folder     = [file for file in Media.query.filter_by(in_folder=media_obj.unique_id).all()]
            media_obj.unique_id = new_uid
        else:
            splitted            = media_obj.unique_id.split("_")
            uid_split           = uidsplit(splitted[0], new_uid)
            media_obj.unique_id = f"{media_obj.filename.split('.')[0]}_{uid_split.uid}"

        db.session.commit()

        for file_in_folder in files_in_folder:
            if not file_in_folder.is_dir():
                file_in_folder.in_folder = new_uid

        db.session.commit()

    return "true"

@main.route("/req_new_acc", methods=["POST"])
def req_new_acc():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        flash("Bitt füllen Sie die Felder aus!", 'error')
        return redirect(url_for("main.request_account"))

    existing_user_request = AccountRequest.query.filter_by(username=username).first()
    existing_user         = User.query.filter_by(username=username).first()

    if existing_user_request:
        flash(f"Der Nutzer \"{existing_user_request.username}\" existiert bereits!", 'error')
        return redirect(url_for("main.request_account"))

    if existing_user:
        flash(f"Der Nutzer \"{existing_user.username}\" existiert bereits!", 'error')
        return redirect(url_for("main.request_account"))

    user_request = AccountRequest(
        username  =username, 
        password  =password,
        date      =datetime.now(),
        ip_address=request.remote_addr
    )

    db.session.add(user_request)
    db.session.commit()

    return redirect(url_for("main.request_account"))


@main.route("/show_account_requests")
@login_required
def show_account_requests():

    if not current_user.is_admin:
        return redirect(url_for("main.index"))

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
def create_request_account():

    request_split = namedtuple("req_split", "state user")
    requests      = request.form.getlist("access")
    
    for req in requests:
        to_check = request_split(req.split()[0], req.split()[1])
        if to_check.state == "yes":
            match = AccountRequest.query.filter_by(username=to_check.user)

            new_user = User(
                match.first().username,
                generate_password_hash(password=match.first().password, method="sha256"),
                "User"
            )

            match.delete()
            db.session.add(new_user)
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
    subject_names     = [(subj, len(Media.query.filter_by(subject=subj).filter_by(name=current_user.username).all())) for subj in reversed(all_subject_names)]

    if not all_subject_names:
        flash("Keine Fächer gefunden.", 'error')

    return render_template(
        "subjects.html",
        subject_names=subject_names
    )


def calc_file_size(path, filename):

    file_path = Path(path, filename)
    if file_path.exists():
        return f"{file_path.stat().st_size / 1e+6:0.2f}"

    return None


def create_url_from_media_path(media_path: str, filename: str) -> str:

    raw_path = f"{media_path.rsplit(f'{abs_path}{nx}{current_user.username}')[1]}/{filename}"
    url_path = f"{url_for('main.index', _external=True)}edit_subject{raw_path}".replace("\\", "/")

    return url_path


@main.route("/edit_subject/<subject>", defaults={"p": None})
@main.route("/edit_subject/<subject>/<path:p>")
@login_required
def edit_subject(subject, p):

    if not p:
        path = Path(abs_path, f"{current_user.username}/{subject}")
    else:
        path = Path(abs_path, f"{current_user.username}/{subject}/{p}")

    filtered_subjects = [sub.subject for sub in Subjects.query.filter_by(name=current_user.username).all()]

    if subject not in filtered_subjects:
        flash(f"Das Fach \"{subject}\" existiert nicht!", "error")
        return redirect(url_for('main.subjects'))

    root_data = Media.query.filter_by(
        name=current_user.username
    ).filter_by(
    subject=subject
    ).filter_by(
        path=str(path)
    ).all()

    data = [
        (
            i + 1, 
            f.filename, 
            calc_file_size(f.path, f.filename),
            True if f.is_dir() else False,
            create_url_from_media_path(f.path, f.filename),
            f.unique_id
        ) 
        
        for i, f in enumerate(root_data)
        #if (full_path := f"{url_for('main.index', _external=True)}edit_subject{f.path.rsplit(f'{str(abs_path)}/{current_user.username}')[0]}/{f.filename}") # LINUX
        #if (full_path := f"{url_for('main.index', _external=True)}edit_subject{f.path.rsplit(f'{str(abs_path)}{nx}{current_user.username}')[1]}/{f.filename}") # WINDOWS
    ]

    if not data:
        flash("Es wurden keine Medien gefunden.", 'media_error')
    
    return render_template(
        "edit_subject.html", 
        subject=subject, 
        data=data
    )


def get_folder_uid(subject, parsed_file_path):

    """
    Determine the folder_uid of the folder where an uploaded file is in.
    """

    # REWRITE THIS SOON PLEASE

    if Path(parsed_file_path) == Path(abs_path, f"{current_user.username}{nx}{subject}"):
       return "root"

    current_path      = f"{current_user.username}{nx}{subject}"
    current_full_path = f"{str(Path(abs_path, current_path))}{nx}"
    current           = parsed_file_path.split(current_full_path)

    if not len(current) > 1:
        return

    current_folder = current[1]

    if nx in current_folder:
        current_folder      = current_folder.split(nx)
        current_folder_name = current_folder[len(current_folder) - 1]
        to_match            = current_folder[0 : len(current_folder) - 1]

        cfullpath           = f"{str(Path(abs_path, current_path))}"
        path_to_filter      = f"{cfullpath}{nx}{f'{nx}'.join(to_match)}"
    else:
        path_to_filter      = f"{str(Path(abs_path, current_path))}"
        current_folder_name = current_folder
        
    folder_uid = Media.query.filter_by(name=current_user.username, subject=subject, filename=current_folder_name, path=path_to_filter, category="folder").first()

    return folder_uid.unique_id

def add_media_data(
    files_to_upload,
    subject,
    username,
    redirect_path,
    disk_path,
    folder_uid
):
    
    if not files_to_upload or files_to_upload[0].filename == "":
        flash("Bitte wählen Sie mindestens eine Datei aus.", 'error')
        return redirect(redirect_path)
    
    all_filenames  = [secure_filename(f.filename) for f in files_to_upload]
    existing_media = [secure_filename(f.filename) for f in Media.query.filter_by(name=username).filter_by(subject=subject).filter_by(path=disk_path).all()]
    existing_files = [filename         for filename in existing_media if filename in all_filenames]
    all_uids       = [obj.unique_id    for obj      in Media.query.filter_by(name=username).all()]

    if existing_files:
        flash(f"Die Datei/en mit dem/n Namen \"{', '.join(existing_files)}\" existier/t/en bereits", 'error')
        return redirect(redirect_path)

    for filename in all_filenames:

        if not allowed_file(filename):
            flash(f"Die Dateiendung \"{filename.rsplit('.')[1]}\" ist nicht erlaubt!", 'error')
            return redirect(redirect_path)

        while True:
            uid = ''.join(choice(chars) for i in range(10))
            if uid not in all_uids:
                break

        new_media_object = Media(
            name     =username, 
            subject  =subject, 
            filename =filename,
            path     =disk_path,
            category ="file",
            unique_id=f"{filename.rsplit('.', 1)[0]}_{uid}",
            in_folder=folder_uid,
            faccess=True
        )
        db.session.add(new_media_object)
    db.session.commit()

    file_path = Path(disk_path)

    for file in files_to_upload:
        if file and allowed_file(file.filename):
            fname = file.filename
            filename = secure_filename(fname)
            file.save(path.join(file_path, filename))

    flash(f"Folgende Datei/en wurde/n erfolgreich hochgeladen und gespeichert: \"{', '.join(all_filenames)}\"", 'upload_success')

    return redirect(redirect_path)

@login_required
@main.route("/add_media", methods=['POST'])
def add_media():
    files            = request.files.getlist('media')
    current_subject  = request.form.get('current_subject')
    file_path_url    = request.form.get("file_path")
    parsed_file_path = parse_file_path(file_path_url, current_subject)
    folder_uid       = get_folder_uid(current_subject, parsed_file_path)

    return add_media_data(
        files_to_upload=files,
        subject=current_subject,
        username=current_user.username,
        redirect_path=file_path_url,
        disk_path=parsed_file_path,
        folder_uid=folder_uid
    )


@login_required
@main.route("/remove_media", methods=['POST'])
def remove_media():

    to_remove        = request.form.getlist('media_to_remove')
    current_subject  = request.form.get('current_subject')
    current_path     = request.form.get("current_path")
    parsed_file_path = parse_file_path(current_path, current_subject)

    if not to_remove:
        flash("Bitte wählen Sie mindestens eine Datei aus.", 'error')
        return redirect(url_for('main.edit_subject', subject=current_subject))

    db_media = [f for f in Media.query.filter_by(name=current_user.username).filter_by(path=parsed_file_path).all() if f.filename in to_remove]
    for media_object in db_media:

        if not media_object.is_dir():
            Media.query.filter_by(unique_id=media_object.unique_id).delete()
        else:
            files_in_folder = [obj for obj in Media.query.filter(Media.path.contains(f"{parsed_file_path}{nx}{media_object.filename}"))] # WINDOWS
            #files_in_folder = [obj for obj in Media.query.filter(Media.path.contains(f"{parsed_file_path}/{media_object.filename}"))] # LINUX
            
            for file_in_folder in files_in_folder:
                Media.query.filter_by(unique_id=file_in_folder.unique_id).delete()

            Media.query.filter_by(unique_id=media_object.unique_id).delete()
            
    db.session.commit()

    for obj in db_media:
        try:
            if obj.category == "file":
                Path(parsed_file_path, obj.filename).unlink()
            else:
                rmtree(Path(parsed_file_path, obj.filename))
        except FileNotFoundError:
            pass

    flash(f"Folgende Medien wurden erfolgreich gelöscht: \"{', '.join(to_remove)}\"", 'media_success')

    return redirect(url_for('main.edit_subject', subject=current_subject))


@main.route("/download/<uid>")
def download_file(uid):
    filtered_uid = Media.query.filter_by(unique_id=uid).first()

    if not filtered_uid:
        return redirect(url_for("main.index"))

    file_path = Path(filtered_uid.path, secure_filename(filtered_uid.filename))
    return send_file(file_path)


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

    filtered_subjects = [subj.subject for subj in Subjects.query.filter_by(name=current_user.username).filter_by(subject=subject).all()]

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


@main.route("/rename_subject", methods=["POST"])
def rename_subject():
    old_subject_name = request.form.get("old_subject_name")
    new_subject_name = request.form.get("new_subject_name")

    subjects_match = Subjects.query.filter_by(name=current_user.username).filter_by(subject=old_subject_name).first()
    media_match    = Media.query.filter_by(subject=old_subject_name).all()

    for mmatch in media_match:
        mmatch.subject = new_subject_name
    db.session.commit()

    if not subjects_match:
        flash(f"Das Fach \"{old_subject_name}\" existiert nicht!", 'error')
        return redirect(url_for('main.subjects'))

    subjects_match.subject = new_subject_name
    db.session.commit()

    move(
        str(Path(abs_path, f"{current_user.username}/{old_subject_name}")), 
        str(Path(abs_path, f"{current_user.username}/{new_subject_name}"))
    )

    return redirect(url_for("main.subjects"))


@main.route("/rename_file", methods=["POST"])
def rename_file():
    old_filename     = request.form.get("old_filename")
    new_filename     = request.form.get("new_filename")
    category         = request.form.get("selector")
    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("rename_path")
    parsed_file_path = parse_file_path(current_path, current_subject)

    match = Media.query.filter_by(
        name=current_user.username
    ).filter_by(
        subject=current_subject
    ).filter_by(
        filename=old_filename
    ).filter_by(
        path=parsed_file_path
    ).first()

    if not match:
        if category == "Ordner":
            flash(f"Der Ordner mit dem Namen \"{old_filename}\" existiert nicht!", 'error')
        else:    
            flash(f"Die Datei mit dem Namen \"{old_filename}\" existiert nicht!", 'error')

        return redirect(current_path)


    if category == "Datei":
        if old_filename.rsplit(".")[1] != new_filename.rsplit(".")[1]:
            flash("Die Dateiendungen stimmen nicht überein!", 'error')
            return redirect(url_for("main.edit_subject", subject=current_subject))

        splitted_uid    = match.unique_id.split("_")
        match.unique_id = f"{new_filename.split('.')[0]}_{splitted_uid[1]}"

    match.filename  = new_filename
    db.session.commit()

    Path(
        parsed_file_path, 
        old_filename
    ).rename(Path(
        parsed_file_path, 
        new_filename)
    )

    return redirect(current_path)

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
