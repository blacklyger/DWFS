from flask          import Blueprint, redirect, url_for, request, flash
from .models        import Media
from .              import db
from flask_login    import login_required, current_user
from pathlib        import Path
from .main          import parse_file_path
from .security      import clean_name, confine, generate_uid, safe_redirect_target

folder = Blueprint('folder', __name__)

@folder.route("/add_folder", methods=["POST"])
@login_required
def add_folder():

    folder_name      = clean_name(request.form.get("folder_name"))
    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("current_path")
    parsed_file_path = parse_file_path(current_path, current_subject)
    redirect_target  = safe_redirect_target(current_path, url_for('main.edit_subject', subject=current_subject))

    if not folder_name:
        flash("Bitte geben Sie einen gültigen Ordnernamen ein!", 'error')
        return redirect(redirect_target)

    if Media.query.filter_by(name=current_user.username, subject=current_subject, path=parsed_file_path, filename=folder_name).first():
        flash(f"Der Ordner \"{folder_name}\" existiert bereits!", 'error')
        return redirect(redirect_target)

    try:
        confine(Path(parsed_file_path, folder_name)).mkdir()
    except FileExistsError:
        flash(f"Der Ordner \"{folder_name}\" existiert bereits!", 'error')
        return redirect(redirect_target)

    new_object = Media(
        current_user.username,
        current_subject,
        folder_name,
        parsed_file_path,
        "folder",
        generate_uid({obj.unique_id for obj in Media.query.with_entities(Media.unique_id)}),
        "/"
    )
    db.session.add(new_object)
    db.session.commit()

    return redirect(redirect_target)
