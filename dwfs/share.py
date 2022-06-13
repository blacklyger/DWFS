from flask          import Blueprint, render_template, redirect, request, url_for, flash
from .models        import User, Subjects, Media
from .              import db
from flask_login    import login_required, current_user
from pathlib        import Path
from werkzeug.utils import secure_filename
from .              import main
from random         import choice

share = Blueprint("share", __name__)
nx = "\\"
#data_path = Path("D:\\XTEC\\computer_science\\software\\DWFS\\dwfs\\data")

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
        file_in_db = Media.query.filter_by(unique_id=file_to_remove)

        file_to_remove_object = file_in_db.first()
        Path(file_in_db.first().path, file_to_remove_object.filename).unlink()
        file_in_db.delete()
        

    flash(f"Removed files: {', '.join(files_to_remove)}", "upload_success")

    return redirect(path)

@share.route("/add_shared_files", methods=["POST"])
def add_shared_files():
    files_to_add = request.files.getlist("media_to_add")
    path           = request.form.get("path")
    folder_uid     = request.form.get("folder_uid")
    folder_name    = request.form.get("folder_name")
    username       = request.form.get("username")
    subject        = request.form.get("subject")
    current_folder = Media.query.filter_by(unique_id=folder_uid).first()
    filepath       = f"{current_folder.path}{nx}{folder_name}"

    return main.add_media_data(
        files_to_upload=files_to_add,
        subject=subject,
        username=username,
        redirect_path=path,
        disk_path=filepath,
        folder_uid=folder_uid
    )

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
