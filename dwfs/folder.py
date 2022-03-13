from flask       import Blueprint, render_template, redirect, url_for, request, flash
from .models     import User, Subjects, Media
from .           import db
from flask_login import login_required, current_user
from pathlib     import Path
from random      import choice
from string      import ascii_letters, digits
from .main       import parse_file_path
from werkzeug.utils import secure_filename

folder     = Blueprint('folder', __name__)
#abs_path   = Path("/home/simon/projects/DWFS/dwfs/data")
chars      = ascii_letters + digits

@folder.route("/add_folder", methods=["POST"])
def add_folder():
    
    folder_name      = secure_filename(request.form.get("folder_name"))
    current_subject  = request.form.get("current_subject")
    current_path     = request.form.get("current_path")
    parsed_file_path = parse_file_path(current_path, current_subject)

    existing_folders = [
        folder.filename 
        for folder in Media.query.filter_by(
            name=current_user.username
        ).filter_by(
            subject=current_subject
        ).filter_by(
            path=parsed_file_path
        ).filter_by(
            category="folder"
        ).filter_by()
    ]

    if folder_name in existing_folders:
        flash(f"Der Ordner \"{folder_name}\" existiert bereits!", 'error')
        return redirect(current_path)

    all_uids = [obj.unique_id for obj in Media.query.filter_by(name=current_user.username).all()]

    while True:
        generated_uid = ''.join(choice(chars) for i in range(10))
        if generated_uid not in all_uids:
            break

    try:
        Path(parsed_file_path, f"{folder_name}").mkdir()
    except FileExistsError:
        flash(f"Der Ordner \"{folder_name}\" existiert bereits!", 'error')
        return redirect(current_path)

    new_object = Media(
        current_user.username,
        current_subject,
        folder_name,
        parsed_file_path,
        "folder",
        generated_uid,
        "/"
    )
    db.session.add(new_object)
    db.session.commit()

    return redirect(current_path)