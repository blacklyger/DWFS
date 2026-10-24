from flask          import Blueprint, render_template, redirect, request, url_for, flash, abort
from .models        import Media
from .              import db
from flask_login    import login_required, current_user
from pathlib        import Path
from .              import main
from .security      import confine

share = Blueprint("share", __name__)


def get_shared_folder(folder_uid):
    folder = Media.query.filter_by(unique_id=folder_uid, category="folder").first()
    if not folder:
        abort(404)
    return folder


def folder_url(folder):
    return url_for('share.share_folder', username=folder.name, subject=folder.subject,
                   folder_name=folder.filename, folder_uid=folder.unique_id)


def may_modify(folder):
    """The owner may always modify, others only if foreign access is enabled."""
    return folder.has_foreign_access() or (current_user.is_authenticated and current_user.username == folder.name)


@share.route("/share/<username>/<subject>/<folder_name>/<folder_uid>")
def share_folder(username, subject, folder_name, folder_uid):

    # Owner, subject and name are always taken from the database, never from the URL.
    folder = get_shared_folder(folder_uid)
    files_in_folder = Media.query.filter_by(name=folder.name, subject=folder.subject, category="file", in_folder=folder.unique_id).all()

    return render_template(
        "folder.html",
        username=folder.name,
        subject=folder.subject,
        folder_name=folder.filename,
        folder_uid=folder.unique_id,
        files=files_in_folder,
        faccess=may_modify(folder)
    )


@share.route("/remove_shared_files", methods=["POST"])
def remove_shared_files():
    folder = get_shared_folder(request.form.get("folder_uid"))

    if not may_modify(folder):
        abort(403)

    removed = []
    for file_uid in request.form.getlist("media_to_remove"):
        # Only files that really live in this shared folder can be removed.
        media_obj = Media.query.filter_by(unique_id=file_uid, category="file", in_folder=folder.unique_id).first()
        if not media_obj:
            continue

        confine(media_obj.path, media_obj.filename).unlink(missing_ok=True)
        db.session.delete(media_obj)
        removed.append(media_obj.filename)

    db.session.commit()

    flash(f"Removed files: {', '.join(removed)}", "upload_success")

    return redirect(folder_url(folder))

@share.route("/add_shared_files", methods=["POST"])
def add_shared_files():
    folder = get_shared_folder(request.form.get("folder_uid"))

    if not may_modify(folder):
        abort(403)

    result = main.add_media_data(
        files_to_upload=request.files.getlist("media_to_add"),
        subject=folder.subject,
        username=folder.name,
        disk_path=str(confine(folder.path, folder.filename)),
        folder_uid=folder.unique_id
    )

    if result == "OK":
        flash("Folgende Datei/en wurde/n erfolgreich hochgeladen und gespeichert.", "upload_success")
    else:
        flash(result, "upload_error")

    return redirect(folder_url(folder))

@share.route("/foreign_access", methods=["POST"])
@login_required
def foreign_access():
    value      = request.form.get("value")
    folder_uid = request.form.get("folder_uid")

    # Only the owner of a folder may change its foreign access setting.
    folder = Media.query.filter_by(unique_id=folder_uid, category="folder", name=current_user.username).first()

    if not folder or value not in ("Ja", "Nein"):
        abort(404)

    folder.set_foreign_access(value == "Ja")

    return f"Foreign access: {'true' if folder.has_foreign_access() else 'false'}"
