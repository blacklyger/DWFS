from flask          import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from .models        import User, Subjects, Media
from .              import db
from flask_login    import login_required, current_user
from werkzeug.utils import secure_filename
from .              import main
from random         import choice
from pathlib        import Path
from json           import dumps

search = Blueprint("search", __name__)
nx = "\\"
#abs_path = Path("D:\\XTEC\\computer_science\\software\\DWFS\\dwfs\\data")

def search_query(query, subject, path):
    
    if query == "":
        return ""

    sres = Media.query.filter_by(
        name=current_user.username
    ).filter_by(
        subject=subject
    ).filter_by(
        path=main.parse_file_path(path, subject)
    ).filter(
        Media.filename.ilike(f"{query}%")
    ).all()

    if path == url_for("main.edit_subject", subject=subject, _external=True):
        sres = Media.query.filter_by(name=current_user.username).filter_by(subject=subject).filter(Media.filename.ilike(f"{'%'.join(query)}%")).all()


    ret = []
    for item in sres:

        r = {}

        r["filename"] = item.filename
        r["category"] = item.category
        r["unique_id"] = item.unique_id
        r["is_dir"] = True if item.category == "folder" else False

        if item.is_dir():
            r["url"]          = main.create_url_from_media_path(item.path, item.filename)
            r["download_url"] = url_for('share.share_folder', username=current_user.username, subject=subject, folder_name=item.filename, folder_uid=item.unique_id, _external=True)

        if not item.is_dir():
            r["file_size"]    = main.calc_file_size(item.path, item.filename)
            r["download_url"] = url_for('main.download_file', uid=item.unique_id, _external=True)

        ret.append(r)

    obj = dumps(ret)

    return obj

@search.route("/search_query", methods=["POST"])
def search_data():

    value           = request.form.get("value")
    current_subject = request.form.get("current_subject")
    path            = request.form.get("path")

    return search_query(query=value, subject=current_subject, path=path)