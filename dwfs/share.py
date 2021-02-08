from flask          import Blueprint, render_template, redirect, request, url_for, flash
from .models        import User, Subjects, Media
from .              import db
from flask_login    import login_required, current_user
from pathlib        import Path
from werkzeug.utils import secure_filename
from .              import main
from random         import choice
from pathlib        import Path

share = Blueprint("share", __name__)
nx = "\\"
data_path = Path("D:\\XTEC\\computer_science\\software\\DWFS\\dwfs\\data")

@share.route("/share/<username>/<subject>/<folder_name>/<folder_uid>")
def share_folder(username, subject, folder_name, folder_uid):

    folder = Media.query.filter_by(unique_id=folder_uid).first()

    if not folder:
        return redirect(url_for('main.index'))

    files_in_folder = Media.query.filter_by(name=username, subject=subject, category="file", in_folder=folder_uid).all()

    return render_template(
        "folder.html",
        username=username,
        subject=subject,
        folder_name=folder_name,
        folder_uid=folder_uid,
        files=files_in_folder,
        faccess=folder.has_foreign_access()
    )


@share.route("/remove_shared_files", methods=["POST"])
def remove_shared_files():
    files_to_remove = request.form.getlist("media_to_remove")
    path            = request.form.get("path")

    for file_to_remove in files_to_remove:
        file_in_db = Media.query.filter_by(unique_id=file_to_remove).delete()

    flash(f"Removed files: {', '.join(files_to_remove)}", "upload_success")

    return redirect(path)

@share.route("/add_shared_files", methods=["POST"])
def add_shared_files():
    files_to_add = request.files.getlist("media_to_add")
    path         = request.form.get("path")
    folder_uid   = request.form.get("folder_uid")
    folder_name  = request.form.get("folder_name")
    username     = request.form.get("username")
    subject      = request.form.get("subject")

    if not files_to_add or files_to_add[0].filename == "":
        flash("Please choose at least one file.", 'upload_error')
        return redirect(path)

    current_folder = Media.query.filter_by(unique_id=folder_uid).first()
    filepath       = f"{current_folder.path}{nx}{folder_name}"

    files_to_upload          = [secure_filename(file.filename) for file in files_to_add]
    files_in_current_folder  = [secure_filename(file.filename) for file in Media.query.filter_by(name=username).filter_by(subject=subject).filter_by(path=filepath).all()]
    already_existing_files   = [filename for filename in files_in_current_folder if filename in files_to_upload]
    all_uids                 = [obj.unique_id for obj in Media.query.filter_by(name=username).all()]

    if already_existing_files:
        flash(f"The file/s already exist/s: {', '.join(already_existing_files)}", "upload_error")
        return redirect(path)

    for file_to_upload in files_to_upload:

        if not main.allowed_file(file_to_upload):
            flash(f"The file extension: \"{file_to_upload.split('.')[1]}\" is not allowed!", "upload_error")
            return redirect(path)

        while True:
            uid = ''.join(choice(main.chars) for _ in range(10))
            if uid not in all_uids:
                break

        new_file = Media(
            name=username,
            subject=subject,
            filename=file_to_upload,
            path=filepath,
            category="file",
            unique_id=f"{file_to_upload.rsplit('.', 1)[0]}_{uid}",
            in_folder=current_folder.unique_id
        )

        db.session.add(new_file)
    db.session.commit()

    path_to_save_file = Path(filepath)

    for file in files_to_add:
        if file and main.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(path_to_save_file.joinpath(filename))

    return redirect(path)

@share.route("/foreign_access", methods=["POST"])
def foreign_access():
    value      = request.form.get("value")
    folder_uid = request.form.get("folder_uid")

    folder = Media.query.filter_by(unique_id=folder_uid).first()

    if not folder:
        return ""

    if (value == "Ja" and folder.has_foreign_access()) or (value == "Nein" and not folder.has_foreign_access()):
        return ""

    if value == "Ja":
        folder.set_foreign_access(True)
        return "Foreign access: true"

    folder.set_foreign_access(False)

    return "Foreign access: false"